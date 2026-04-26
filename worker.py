from celery import Celery
from celery.signals import task_failure, task_retry
import os
import celeryconfig
import pandas as pd
import numpy as np
from sklearn.impute import SimpleImputer
from sklearn.ensemble import IsolationForest
from sklearn.neighbors import LocalOutlierFactor
from sklearn.cluster import DBSCAN, KMeans
from sklearn.mixture import GaussianMixture
from sklearn.metrics import pairwise_distances
from sklearn.preprocessing import MinMaxScaler
from repositories import AuditRepository, TaskResultRepository

app = Celery('worker')
app.config_from_object(celeryconfig)

task_result_repo = TaskResultRepository()
audit_repo = AuditRepository()

REQUIRED_TENANT_CONTEXT_FIELDS = {"tenant_id", "actor_id", "roles", "request_id", "plan_tier"}
PLAN_TIER_CONCURRENCY_LIMITS = {
    "standard": int(os.getenv("TENANT_QUOTA_STANDARD", "2")),
    "pro": int(os.getenv("TENANT_QUOTA_PRO", "5")),
    "enterprise": int(os.getenv("TENANT_QUOTA_ENTERPRISE", "10")),
}


class TenantQuotaExceededError(ValueError):
    pass


def validate_tenant_context(tenant_context):
    if not isinstance(tenant_context, dict):
        raise ValueError("tenant_context must be a dict")

    missing = REQUIRED_TENANT_CONTEXT_FIELDS - set(tenant_context)
    if missing:
        raise ValueError(f"tenant_context missing required fields: {sorted(missing)}")

    if not tenant_context["tenant_id"] or not tenant_context["actor_id"]:
        raise ValueError("tenant_context requires tenant_id and actor_id")

    roles = tenant_context["roles"]
    if not isinstance(roles, list) or not roles:
        raise ValueError("tenant_context roles must be a non-empty list")

    return tenant_context


def _build_idempotency_key(tenant_context, algorithm, workflow_name):
    return (
        f"{tenant_context['tenant_id']}:"
        f"{tenant_context['request_id']}:"
        f"{algorithm}:{workflow_name}"
    )


def _workflow_quota_for_tier(plan_tier):
    return PLAN_TIER_CONCURRENCY_LIMITS.get(plan_tier, PLAN_TIER_CONCURRENCY_LIMITS["standard"])


def _prepare_task_execution(task_id, tenant_context, algorithm, params, workflow_name):
    idempotency_key = _build_idempotency_key(tenant_context, algorithm, workflow_name)
    existing = task_result_repo.get_task_by_idempotency(
        tenant_id=tenant_context["tenant_id"],
        idempotency_key=idempotency_key,
    )

    if existing and existing.get("status") == "SUCCESS" and isinstance(existing.get("result_payload"), dict):
        audit_repo.log_event(
            tenant_id=tenant_context["tenant_id"],
            actor_id=tenant_context["actor_id"],
            action="task.idempotent_hit",
            resource_type="task",
            resource_id=existing.get("task_id", task_id),
            result="success",
            request_id=tenant_context["request_id"],
            details={"workflow": workflow_name, "algorithm": algorithm},
        )
        cached = dict(existing["result_payload"])
        cached.setdefault("tenant_id", tenant_context["tenant_id"])
        cached.setdefault("request_id", tenant_context["request_id"])
        cached["_id"] = existing.get("task_id", task_id)
        return idempotency_key, cached

    active_count = task_result_repo.count_active_tasks_for_tenant(tenant_id=tenant_context["tenant_id"])
    quota = _workflow_quota_for_tier(tenant_context["plan_tier"])
    if active_count >= quota:
        raise TenantQuotaExceededError(
            f"Tenant quota exceeded: active={active_count}, quota={quota}"
        )

    task_result_repo.upsert_task_result(
        tenant_id=tenant_context["tenant_id"],
        task_id=task_id,
        status="STARTED",
        idempotency_key=idempotency_key,
        algorithm=algorithm,
        params=params,
        created_by=tenant_context["actor_id"],
        request_id=tenant_context["request_id"],
        plan_tier=tenant_context["plan_tier"],
    )
    return idempotency_key, None


def _upsert_retry_result(task_id, tenant_context, error_message):
    task_result_repo.upsert_task_result(
        tenant_id=tenant_context["tenant_id"],
        task_id=task_id,
        status="RETRY",
        created_by=tenant_context["actor_id"],
        request_id=tenant_context["request_id"],
        plan_tier=tenant_context["plan_tier"],
        error=error_message,
    )


def _upsert_failure_result(task_id, tenant_context, error_message):
    task_result_repo.upsert_task_result(
        tenant_id=tenant_context["tenant_id"],
        task_id=task_id,
        status="FAILURE",
        created_by=tenant_context["actor_id"],
        request_id=tenant_context["request_id"],
        plan_tier=tenant_context["plan_tier"],
        error=error_message,
    )
    audit_repo.log_event(
        tenant_id=tenant_context["tenant_id"],
        actor_id=tenant_context["actor_id"],
        action="task.failure",
        resource_type="task",
        resource_id=task_id,
        result="failure",
        request_id=tenant_context["request_id"],
        details={"error": error_message},
    )

# Celery ???¤ì 
def _upsert_success_result(task_id, tenant_context, algorithm, params, result, idempotency_key=None):
    task_result_repo.upsert_task_result(
        tenant_id=tenant_context["tenant_id"],
        task_id=task_id,
        status="SUCCESS",
        idempotency_key=idempotency_key,
        algorithm=algorithm,
        params=params,
        created_by=tenant_context["actor_id"],
        request_id=tenant_context["request_id"],
        plan_tier=tenant_context["plan_tier"],
        result_payload=result,
    )
    audit_repo.log_event(
        tenant_id=tenant_context["tenant_id"],
        actor_id=tenant_context["actor_id"],
        action="task.complete",
        resource_type="task",
        resource_id=task_id,
        result="success",
        request_id=tenant_context["request_id"],
        details={"algorithm": algorithm},
    )

@app.task(bind=True, autoretry_for=(Exception,), dont_autoretry_for=(ValueError,), retry_backoff=True, retry_jitter=True, retry_kwargs={"max_retries": 3})
def run_timeseries_workflow(self, df, algorithm, params, tenant_context):
    tenant_context = validate_tenant_context(tenant_context)
    task_id = self.request.id
    idempotency_key, cached_result = _prepare_task_execution(task_id, tenant_context, algorithm, params, "timeseries")
    if cached_result is not None:
        return cached_result
    print(
        f"tenant_id={tenant_context['tenant_id']} "
        f"request_id={tenant_context['request_id']} "
        f"workflow=timeseries"
    )
    df = pd.DataFrame(df)

    df.set_index(df.columns[0], inplace=True)
    index = df.index.tolist()
    index = [str(i) for i in index] 
    df = df.iloc[:, 0:] 
    X = df
    
    result = {}
    root_cause_scores = {}

    # Prefect ??ìë¦¬ì¦ ?í¬?ë¡???¸ì¶
    if algorithm == 'IsolationForest':
        model = IsolationForest(max_samples=params["max_samples"], n_jobs=params["n_jobs"], contamination=params["contamination"])
        model.fit(X)
        y_pred = model.predict(X)
        outlier_indices = np.where(y_pred == -1)[0].tolist()
        outlier_scores = -model.decision_function(X)
        scaler = MinMaxScaler()
        outlier_probabilities = scaler.fit_transform(outlier_scores.reshape(-1, 1)).flatten().tolist()
    elif algorithm == 'GMM':
        model = GaussianMixture(n_init=params["n_init"], n_components=params["n_components"], random_state=params["random_state"], init_params=params["init_params"])
        model.fit(X)
        probs = model.predict_proba(X)
        prob_threshold = np.percentile(probs.max(axis=1), 5)
        outlier_indices = np.where(probs.max(axis=1) < prob_threshold)[0].tolist()
        outlier_probabilities = (1 - probs.max(axis=1)[probs.max(axis=1) < prob_threshold]).tolist()
    
    
    # ëª¨ë  ?¸ë±?¤ì ???root cause score ê³ì°
    for timestamp in X.index:
        # ê°?timestamp?ì feature-wise ?¸ì°¨ ê³ì°
        score = np.abs(X.loc[timestamp].values - X.mean(axis=0).values)
    
        # score? X.columns??ê¸¸ì´ë¥?ë§ì¶¤
        if len(score) != len(X.columns):
            # X.columns ?¬ê¸°??ë§ê² scoreë¥?ì¡°ì  (resize ?¬ì©)
            score = np.resize(score, len(X.columns))
        # ?ê·??ê³¼ì 
        score = (score - np.min(score)) / (np.max(score) - np.min(score) + 1e-9)  # ?ê·??
    
        # ?¤ì ??ë²??ì¸?´ì scoreê° 1ì°¨ì?¸ì? ?ì¸
        if score.ndim > 1:
            score = score.flatten()  # 1ì°¨ì?¼ë¡ ?í??
    
        # scoreë¥??ë¦¬ì¦ë¡ ë³?í??root_cause_scores?????
        score_series = pd.Series(score, index=X.columns)
        root_cause_scores[str(timestamp)] = score_series.to_dict()  # ???


    # MongoDB????¥í  ì§ë ¬??ê°?¥í ê²°ê³¼ë§????
    result['outlier_indices'] = outlier_indices
    result['outlier_probabilities'] = outlier_probabilities
    result['root_cause_scores'] = root_cause_scores
    result['index'] = index
    result['tenant_id'] = tenant_context['tenant_id']
    result['request_id'] = tenant_context['request_id']
    
    
    # MongoDB??ê²°ê³¼ ???
    _upsert_success_result(task_id, tenant_context, algorithm, params, result, idempotency_key=idempotency_key)
    result["_id"] = task_id

    return result

@app.task(bind=True, autoretry_for=(Exception,), dont_autoretry_for=(ValueError,), retry_backoff=True, retry_jitter=True, retry_kwargs={"max_retries": 3})
def run_categorical_workflow(self, df, algorithm, params, tenant_context):
    tenant_context = validate_tenant_context(tenant_context)
    task_id = self.request.id
    idempotency_key, cached_result = _prepare_task_execution(task_id, tenant_context, algorithm, params, "categorical")
    if cached_result is not None:
        return cached_result
    print(
        f"tenant_id={tenant_context['tenant_id']} "
        f"request_id={tenant_context['request_id']} "
        f"workflow=categorical"
    )
    df = pd.DataFrame(df)
    # NaN ê°ì ì¤ìê°ì¼ë¡??ì²?(?ë dropnaë¡??ê±°)
    imputer = SimpleImputer(strategy='median')
    df = pd.DataFrame(imputer.fit_transform(df), columns=df.columns)
    
    # 0ë²ì§¸ ?´ì ë¬¸ì??ê·¸ë?ë¡??¸ë±?¤ë¡ ?¤ì 
    df.set_index(df.columns[0], inplace=True)
    index = df.index.tolist()
    index = [str(i) for i in index] 
    df = df.iloc[:, 0:] 
    X = df
    
    result = {}
    root_cause_scores = {}
    
    # Prefect ì¹´íê³ ë¦¬ ?í¬?ë¡???¸ì¶
    if algorithm == 'LOF':
        model = LocalOutlierFactor(n_neighbors=params["n_neighbors"], n_jobs=params["n_jobs"], contamination=params["contamination"])
        y_pred = model.fit_predict(X)
        outlier_indices = np.where(y_pred == -1)[0].tolist()
        outlier_scores = -model.negative_outlier_factor_
        scaler = MinMaxScaler()
        outlier_probabilities = scaler.fit_transform(outlier_scores.reshape(-1, 1)).flatten().tolist()
    
    elif algorithm == 'DBSCAN':
        model = DBSCAN(eps=params["eps"], min_samples=params["min_samples"], n_jobs=params["n_jobs"])
        y_pred = model.fit_predict(X)
        outlier_indices = np.where(y_pred == -1)[0].tolist()
        
        # Check if there are any core samples and outliers
        core_sample_indices = model.core_sample_indices_
        if len(core_sample_indices) == 0 or len(outlier_indices) == 0:
            # If there are no core samples or no outliers, avoid calculating distances
            outlier_scores = [0] * len(outlier_indices)  # Assign a default score of 0 for all outliers
            outlier_probabilities = [0] * len(outlier_indices)  # Assign a default probability of 0
        else:
            core_samples = X.iloc[core_sample_indices]
            outlier_samples = X.iloc[outlier_indices]

        
            distances = pairwise_distances(outlier_samples, core_samples, metric='euclidean')
            outlier_scores = np.min(distances, axis=1)
        
            scaler = MinMaxScaler()
            outlier_probabilities = scaler.fit_transform(outlier_scores.reshape(-1, 1)).flatten().tolist()
    

    # ëª¨ë  ?¸ë±?¤ì ???root cause score ê³ì°
    for timestamp in X.index:
        # ê°?timestamp?ì feature-wise ?¸ì°¨ ê³ì°
        score = np.abs(X.loc[timestamp].values - X.mean(axis=0).values)
    
        # score? X.columns??ê¸¸ì´ë¥?ë§ì¶¤
        if len(score) != len(X.columns):
            # X.columns ?¬ê¸°??ë§ê² scoreë¥?ì¡°ì  (resize ?¬ì©)
            score = np.resize(score, len(X.columns))
        # ?ê·??ê³¼ì 
        score = (score - np.min(score)) / (np.max(score) - np.min(score) + 1e-9)  # ?ê·??
    
        # ?¤ì ??ë²??ì¸?´ì scoreê° 1ì°¨ì?¸ì? ?ì¸
        if score.ndim > 1:
            score = score.flatten()  # 1ì°¨ì?¼ë¡ ?í??
    
        # scoreë¥??ë¦¬ì¦ë¡ ë³?í??root_cause_scores?????
        score_series = pd.Series(score, index=X.columns)
        root_cause_scores[str(timestamp)] = score_series.to_dict()  # ???

        
    # MongoDB????¥í  ì§ë ¬??ê°?¥í ê²°ê³¼ë§????
    result['outlier_indices'] = outlier_indices
    result['outlier_probabilities'] = outlier_probabilities
    result['root_cause_scores'] = root_cause_scores
    result['index'] = index
    result['tenant_id'] = tenant_context['tenant_id']
    result['request_id'] = tenant_context['request_id']

    
    
    # MongoDB??ê²°ê³¼ ???
    _upsert_success_result(task_id, tenant_context, algorithm, params, result, idempotency_key=idempotency_key)
    result["_id"] = task_id

    return result

@app.task(bind=True, autoretry_for=(Exception,), dont_autoretry_for=(ValueError,), retry_backoff=True, retry_jitter=True, retry_kwargs={"max_retries": 3})
def run_numerical_workflow(self, df, algorithm, params, tenant_context):
    tenant_context = validate_tenant_context(tenant_context)
    task_id = self.request.id
    idempotency_key, cached_result = _prepare_task_execution(task_id, tenant_context, algorithm, params, "numerical")
    if cached_result is not None:
        return cached_result
    print(
        f"tenant_id={tenant_context['tenant_id']} "
        f"request_id={tenant_context['request_id']} "
        f"workflow=numerical"
    )
    df = pd.DataFrame(df)
    # NaN ê°ì ì¤ìê°ì¼ë¡??ì²?(?ë dropnaë¡??ê±°)
    imputer = SimpleImputer(strategy='median')
    df = pd.DataFrame(imputer.fit_transform(df), columns=df.columns)

    # 0ë²ì§¸ ?´ì ë¬¸ì??ê·¸ë?ë¡??¸ë±?¤ë¡ ?¤ì 
    df.set_index(df.columns[0], inplace=True)

    index = df.index.tolist()
    index = [str(i) for i in index] 
    df = df.iloc[:, 0:] 
    X = df

    result = {}
    root_cause_scores = {}
    
    # Prefect ì¹´íê³ ë¦¬ ?í¬?ë¡???¸ì¶
    if algorithm == 'IsolationForest':
        model = IsolationForest(max_samples=params["max_samples"], n_jobs=params["n_jobs"], contamination=params["contamination"])
        model.fit(X)
        y_pred = model.predict(X)
        outlier_indices = np.where(y_pred == -1)[0].tolist()
        outlier_scores = -model.decision_function(X)
        scaler = MinMaxScaler()
        outlier_probabilities = scaler.fit_transform(outlier_scores.reshape(-1, 1)).flatten().tolist()
    elif algorithm == 'GMM':
        model = GaussianMixture(n_init=params["n_init"], n_components=params["n_components"], random_state=params["random_state"], init_params=params["init_params"])
        model.fit(X)
        probs = model.predict_proba(X)
        prob_threshold = np.percentile(probs.max(axis=1), 5)
        outlier_indices = np.where(probs.max(axis=1) < prob_threshold)[0].tolist()
        outlier_probabilities = (1 - probs.max(axis=1)[probs.max(axis=1) < prob_threshold]).tolist()
    elif algorithm == 'DBSCAN':
        model = DBSCAN(eps=params["eps"], min_samples=params["min_samples"], n_jobs=params["n_jobs"])
        y_pred = model.fit_predict(X)
        outlier_indices = np.where(y_pred == -1)[0].tolist()
        
        # Check if there are any core samples and outliers
        core_sample_indices = model.core_sample_indices_
        if len(core_sample_indices) == 0 or len(outlier_indices) == 0:
            # If there are no core samples or no outliers, avoid calculating distances
            outlier_scores = [0] * len(outlier_indices)  # Assign a default score of 0 for all outliers
            outlier_probabilities = [0] * len(outlier_indices)  # Assign a default probability of 0
        else:
            core_samples = X.iloc[core_sample_indices]
            outlier_samples = X.iloc[outlier_indices]

        
            distances = pairwise_distances(outlier_samples, core_samples, metric='euclidean')
            outlier_scores = np.min(distances, axis=1)
        
            scaler = MinMaxScaler()
            outlier_probabilities = scaler.fit_transform(outlier_scores.reshape(-1, 1)).flatten().tolist()
    elif algorithm == 'LOF':
        model = LocalOutlierFactor(n_neighbors=params["n_neighbors"], n_jobs=params["n_jobs"], contamination=params["contamination"])
        y_pred = model.fit_predict(X)
        outlier_indices = np.where(y_pred == -1)[0].tolist()
        outlier_scores = -model.negative_outlier_factor_
        scaler = MinMaxScaler()
        outlier_probabilities = scaler.fit_transform(outlier_scores.reshape(-1, 1)).flatten().tolist()
    elif algorithm == 'KMeans':
        model = KMeans(n_init=params["n_init"], n_clusters=params["n_clusters"])
        model.fit(X)
        y_pred = model.predict(X)
        
        distances = np.min(model.transform(X), axis=1)
        threshold = np.percentile(distances, 95)
        outlier_indices = np.where(distances > threshold)[0].tolist()
        outlier_scores = distances[distances > threshold]
        
        scaler = MinMaxScaler()
        outlier_probabilities = scaler.fit_transform(outlier_scores.reshape(-1, 1)).flatten().tolist()

        
    for timestamp in X.index:
        # ê°?timestamp?ì feature-wise ?¸ì°¨ ê³ì°
        score = np.abs(X.loc[timestamp].values - X.mean(axis=0).values)
    
        # score? X.columns??ê¸¸ì´ë¥?ë§ì¶¤
        if len(score) != len(X.columns):
            # X.columns ?¬ê¸°??ë§ê² scoreë¥?ì¡°ì  (resize ?¬ì©)
            score = np.resize(score, len(X.columns))
        # ?ê·??ê³¼ì 
        score = (score - np.min(score)) / (np.max(score) - np.min(score) + 1e-9)  # ?ê·??
    
        # ?¤ì ??ë²??ì¸?´ì scoreê° 1ì°¨ì?¸ì? ?ì¸
        if score.ndim > 1:
            score = score.flatten()  # 1ì°¨ì?¼ë¡ ?í??
    
        # scoreë¥??ë¦¬ì¦ë¡ ë³?í??root_cause_scores?????
        score_series = pd.Series(score, index=X.columns)
        root_cause_scores[str(timestamp)] = score_series.to_dict()  # ???
        
    # MongoDB????¥í  ì§ë ¬??ê°?¥í ê²°ê³¼ë§????
    result['outlier_indices'] = outlier_indices
    result['outlier_probabilities'] = outlier_probabilities
    result['root_cause_scores'] = root_cause_scores
    result['index'] = index
    result['tenant_id'] = tenant_context['tenant_id']
    result['request_id'] = tenant_context['request_id']

    
    
    # MongoDB??ê²°ê³¼ ???
    _upsert_success_result(task_id, tenant_context, algorithm, params, result, idempotency_key=idempotency_key)
    result["_id"] = task_id

    return result


def _extract_tenant_context_from_task_args(args):
    if not args or len(args) < 4:
        return None
    tenant_context = args[3]
    if isinstance(tenant_context, dict):
        return tenant_context
    return None


@task_retry.connect
def on_task_retry(request=None, reason=None, einfo=None, **kwargs):
    tenant_context = _extract_tenant_context_from_task_args(getattr(request, "args", None))
    if not tenant_context:
        return
    task_id = getattr(request, "id", None)
    if not task_id:
        return
    _upsert_retry_result(task_id, tenant_context, str(reason))


@task_failure.connect
def on_task_failure(task_id=None, exception=None, args=None, kwargs=None, einfo=None, **extra):
    tenant_context = _extract_tenant_context_from_task_args(args)
    if not tenant_context or not task_id:
        return
    _upsert_failure_result(task_id, tenant_context, str(exception))
