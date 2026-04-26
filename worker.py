from celery import Celery
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

# Celery ???¤ì •
def _upsert_success_result(task_id, tenant_context, algorithm, params, result):
    task_result_repo.upsert_task_result(
        tenant_id=tenant_context["tenant_id"],
        task_id=task_id,
        status="SUCCESS",
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

@app.task(bind=True)
def run_timeseries_workflow(self, df, algorithm, params, tenant_context):
    tenant_context = validate_tenant_context(tenant_context)
    task_id = self.request.id
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

    # Prefect ?€?„ì‹œë¦¬ì¦ˆ ?Œí¬?Œë¡œ???¸ì¶œ
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
    
    
    # ëª¨ë“  ?¸ë±?¤ì— ?€??root cause score ê³„ì‚°
    for timestamp in X.index:
        # ê°?timestamp?ì„œ feature-wise ?¸ì°¨ ê³„ì‚°
        score = np.abs(X.loc[timestamp].values - X.mean(axis=0).values)
    
        # score?€ X.columns??ê¸¸ì´ë¥?ë§ì¶¤
        if len(score) != len(X.columns):
            # X.columns ?¬ê¸°??ë§ê²Œ scoreë¥?ì¡°ì • (resize ?¬ìš©)
            score = np.resize(score, len(X.columns))
        # ?•ê·œ??ê³¼ì •
        score = (score - np.min(score)) / (np.max(score) - np.min(score) + 1e-9)  # ?•ê·œ??
    
        # ?¤ì‹œ ??ë²??•ì¸?´ì„œ scoreê°€ 1ì°¨ì›?¸ì? ?•ì¸
        if score.ndim > 1:
            score = score.flatten()  # 1ì°¨ì›?¼ë¡œ ?‰íƒ„??
    
        # scoreë¥??œë¦¬ì¦ˆë¡œ ë³€?˜í•˜??root_cause_scores???€??
        score_series = pd.Series(score, index=X.columns)
        root_cause_scores[str(timestamp)] = score_series.to_dict()  # ?€??


    # MongoDB???€?¥í•  ì§ë ¬??ê°€?¥í•œ ê²°ê³¼ë§??€??
    result['outlier_indices'] = outlier_indices
    result['outlier_probabilities'] = outlier_probabilities
    result['root_cause_scores'] = root_cause_scores
    result['index'] = index
    result['tenant_id'] = tenant_context['tenant_id']
    result['request_id'] = tenant_context['request_id']
    
    
    # MongoDB??ê²°ê³¼ ?€??
    _upsert_success_result(task_id, tenant_context, algorithm, params, result)
    result["_id"] = task_id

    return result

@app.task(bind=True)
def run_categorical_workflow(self, df, algorithm, params, tenant_context):
    tenant_context = validate_tenant_context(tenant_context)
    task_id = self.request.id
    print(
        f"tenant_id={tenant_context['tenant_id']} "
        f"request_id={tenant_context['request_id']} "
        f"workflow=categorical"
    )
    df = pd.DataFrame(df)
    # NaN ê°’ì„ ì¤‘ì•™ê°’ìœ¼ë¡??€ì²?(?ëŠ” dropnaë¡??œê±°)
    imputer = SimpleImputer(strategy='median')
    df = pd.DataFrame(imputer.fit_transform(df), columns=df.columns)
    
    # 0ë²ˆì§¸ ?´ì„ ë¬¸ì??ê·¸ë?ë¡??¸ë±?¤ë¡œ ?¤ì •
    df.set_index(df.columns[0], inplace=True)
    index = df.index.tolist()
    index = [str(i) for i in index] 
    df = df.iloc[:, 0:] 
    X = df
    
    result = {}
    root_cause_scores = {}
    
    # Prefect ì¹´í…Œê³ ë¦¬ ?Œí¬?Œë¡œ???¸ì¶œ
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
    

    # ëª¨ë“  ?¸ë±?¤ì— ?€??root cause score ê³„ì‚°
    for timestamp in X.index:
        # ê°?timestamp?ì„œ feature-wise ?¸ì°¨ ê³„ì‚°
        score = np.abs(X.loc[timestamp].values - X.mean(axis=0).values)
    
        # score?€ X.columns??ê¸¸ì´ë¥?ë§ì¶¤
        if len(score) != len(X.columns):
            # X.columns ?¬ê¸°??ë§ê²Œ scoreë¥?ì¡°ì • (resize ?¬ìš©)
            score = np.resize(score, len(X.columns))
        # ?•ê·œ??ê³¼ì •
        score = (score - np.min(score)) / (np.max(score) - np.min(score) + 1e-9)  # ?•ê·œ??
    
        # ?¤ì‹œ ??ë²??•ì¸?´ì„œ scoreê°€ 1ì°¨ì›?¸ì? ?•ì¸
        if score.ndim > 1:
            score = score.flatten()  # 1ì°¨ì›?¼ë¡œ ?‰íƒ„??
    
        # scoreë¥??œë¦¬ì¦ˆë¡œ ë³€?˜í•˜??root_cause_scores???€??
        score_series = pd.Series(score, index=X.columns)
        root_cause_scores[str(timestamp)] = score_series.to_dict()  # ?€??

        
    # MongoDB???€?¥í•  ì§ë ¬??ê°€?¥í•œ ê²°ê³¼ë§??€??
    result['outlier_indices'] = outlier_indices
    result['outlier_probabilities'] = outlier_probabilities
    result['root_cause_scores'] = root_cause_scores
    result['index'] = index
    result['tenant_id'] = tenant_context['tenant_id']
    result['request_id'] = tenant_context['request_id']

    
    
    # MongoDB??ê²°ê³¼ ?€??
    _upsert_success_result(task_id, tenant_context, algorithm, params, result)
    result["_id"] = task_id

    return result

@app.task(bind=True)
def run_numerical_workflow(self, df, algorithm, params, tenant_context):
    tenant_context = validate_tenant_context(tenant_context)
    task_id = self.request.id
    print(
        f"tenant_id={tenant_context['tenant_id']} "
        f"request_id={tenant_context['request_id']} "
        f"workflow=numerical"
    )
    df = pd.DataFrame(df)
    # NaN ê°’ì„ ì¤‘ì•™ê°’ìœ¼ë¡??€ì²?(?ëŠ” dropnaë¡??œê±°)
    imputer = SimpleImputer(strategy='median')
    df = pd.DataFrame(imputer.fit_transform(df), columns=df.columns)

    # 0ë²ˆì§¸ ?´ì„ ë¬¸ì??ê·¸ë?ë¡??¸ë±?¤ë¡œ ?¤ì •
    df.set_index(df.columns[0], inplace=True)

    index = df.index.tolist()
    index = [str(i) for i in index] 
    df = df.iloc[:, 0:] 
    X = df

    result = {}
    root_cause_scores = {}
    
    # Prefect ì¹´í…Œê³ ë¦¬ ?Œí¬?Œë¡œ???¸ì¶œ
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
        # ê°?timestamp?ì„œ feature-wise ?¸ì°¨ ê³„ì‚°
        score = np.abs(X.loc[timestamp].values - X.mean(axis=0).values)
    
        # score?€ X.columns??ê¸¸ì´ë¥?ë§ì¶¤
        if len(score) != len(X.columns):
            # X.columns ?¬ê¸°??ë§ê²Œ scoreë¥?ì¡°ì • (resize ?¬ìš©)
            score = np.resize(score, len(X.columns))
        # ?•ê·œ??ê³¼ì •
        score = (score - np.min(score)) / (np.max(score) - np.min(score) + 1e-9)  # ?•ê·œ??
    
        # ?¤ì‹œ ??ë²??•ì¸?´ì„œ scoreê°€ 1ì°¨ì›?¸ì? ?•ì¸
        if score.ndim > 1:
            score = score.flatten()  # 1ì°¨ì›?¼ë¡œ ?‰íƒ„??
    
        # scoreë¥??œë¦¬ì¦ˆë¡œ ë³€?˜í•˜??root_cause_scores???€??
        score_series = pd.Series(score, index=X.columns)
        root_cause_scores[str(timestamp)] = score_series.to_dict()  # ?€??
        
    # MongoDB???€?¥í•  ì§ë ¬??ê°€?¥í•œ ê²°ê³¼ë§??€??
    result['outlier_indices'] = outlier_indices
    result['outlier_probabilities'] = outlier_probabilities
    result['root_cause_scores'] = root_cause_scores
    result['index'] = index
    result['tenant_id'] = tenant_context['tenant_id']
    result['request_id'] = tenant_context['request_id']

    
    
    # MongoDB??ê²°ê³¼ ?€??
    _upsert_success_result(task_id, tenant_context, algorithm, params, result)
    result["_id"] = task_id

    return result
