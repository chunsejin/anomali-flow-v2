import json
import logging
import os
from typing import Any, Dict, List, Optional, Union
from uuid import uuid4

from celery.result import AsyncResult
from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

import celeryconfig
from auth import RequestContext, require_request_context, require_roles
from repositories import (
    ActionRecommendationRepository,
    AuditRepository,
    CausalReportRepository,
    TaskResultRepository,
)
from worker import run_categorical_workflow, run_numerical_workflow, run_timeseries_workflow


app = FastAPI()
task_result_repo = TaskResultRepository()
audit_repo = AuditRepository()
causal_report_repo = CausalReportRepository()
action_recommendation_repo = ActionRecommendationRepository()
POLICY_VERSION = "v1"
logger = logging.getLogger("anomali.main")

DEFAULT_CORS_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]
cors_origins = [
    origin.strip()
    for origin in os.getenv("CORS_ALLOW_ORIGINS", ",".join(DEFAULT_CORS_ORIGINS)).split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def slog(event: str, **fields: Any) -> None:
    payload = {"event": event, **fields}
    logger.info(json.dumps(payload, ensure_ascii=False))


class TaskRequest(BaseModel):
    # Accept both row-array payloads (frontend CSV upload) and dict payloads (legacy callers).
    df: Union[List[Dict[str, Any]], Dict[str, Any]]
    algorithm: str
    params: Dict[str, Any]


class ErrorPayload(BaseModel):
    code: str
    message: str
    details: Optional[dict[str, Any]] = None


def build_success_response(context: RequestContext, data: dict[str, Any]) -> dict[str, Any]:
    return {
        "tenant_id": context.tenant_id,
        "submitted_by": context.actor_id,
        "trace_id": context.request_id,
        "request_id": context.request_id,
        "policy_version": POLICY_VERSION,
        "data": data,
        "error": None,
    }


def build_error_response(
    *,
    trace_id: str,
    code: str,
    message: str,
    details: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    return {
        "tenant_id": None,
        "submitted_by": None,
        "trace_id": trace_id,
        "request_id": trace_id,
        "policy_version": POLICY_VERSION,
        "data": None,
        "error": ErrorPayload(code=code, message=message, details=details).dict(),
    }


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    trace_id = request.headers.get("x-request-id") or str(uuid4())
    return JSONResponse(
        status_code=exc.status_code,
        content=build_error_response(
            trace_id=trace_id,
            code=f"HTTP_{exc.status_code}",
            message=str(exc.detail),
            details=None,
        ),
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    trace_id = request.headers.get("x-request-id") or str(uuid4())
    return JSONResponse(
        status_code=500,
        content=build_error_response(
            trace_id=trace_id,
            code="INTERNAL_SERVER_ERROR",
            message="Unexpected server error",
            details={"error": str(exc)},
        ),
    )


@app.post("/tasks", response_model=dict)
def run_task(
    request: TaskRequest,
    background_tasks: BackgroundTasks,
    context: RequestContext = Depends(require_request_context),
):
    require_roles(context, {"tenant_admin", "ml_operator"})
    tenant_context = context.as_tenant_context()
    slog(
        "task_submit_requested",
        tenant_id=context.tenant_id,
        actor_id=context.actor_id,
        request_id=context.request_id,
        algorithm=request.algorithm,
    )

    data_type = str(request.params.get("data_type", "")).strip().lower()
    algorithm = request.algorithm
    timeseries_algorithms = {"IsolationForest", "GMM"}
    categorical_algorithms = {"LOF", "DBSCAN"}
    numerical_algorithms = {"IsolationForest", "GMM", "DBSCAN", "LOF", "KMeans"}

    if data_type == "time_series":
        if algorithm not in timeseries_algorithms:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported algorithm '{algorithm}' for data_type 'time_series'",
            )
        task = run_timeseries_workflow.delay(request.df, algorithm, request.params, tenant_context)
    elif data_type == "categorical":
        if algorithm not in categorical_algorithms:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported algorithm '{algorithm}' for data_type 'categorical'",
            )
        task = run_categorical_workflow.delay(request.df, algorithm, request.params, tenant_context)
    elif data_type == "numerical":
        if algorithm not in numerical_algorithms:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported algorithm '{algorithm}' for data_type 'numerical'",
            )
        task = run_numerical_workflow.delay(request.df, algorithm, request.params, tenant_context)
    else:
        # Backward-compatible fallback when data_type is absent.
        if algorithm in categorical_algorithms:
            task = run_categorical_workflow.delay(request.df, algorithm, request.params, tenant_context)
        else:
            task = run_numerical_workflow.delay(request.df, algorithm, request.params, tenant_context)

    task_result_repo.create_submitted_task(
        tenant_id=context.tenant_id,
        task_id=task.id,
        algorithm=request.algorithm,
        params=request.params,
        created_by=context.actor_id,
        request_id=context.request_id,
        plan_tier=context.plan_tier,
    )
    slog(
        "task_enqueued",
        tenant_id=context.tenant_id,
        actor_id=context.actor_id,
        request_id=context.request_id,
        task_id=task.id,
        algorithm=request.algorithm,
    )
    audit_repo.log_event(
        tenant_id=context.tenant_id,
        actor_id=context.actor_id,
        action="task.enqueue",
        resource_type="task",
        resource_id=task.id,
        result="success",
        request_id=context.request_id,
        details={"algorithm": request.algorithm},
    )

    background_tasks.add_task(check_task_status, task.id)
    return build_success_response(
        context,
        {
            "task_id": task.id,
            "status": "PENDING",
        },
    )


def check_task_status(task_id: str):
    result = AsyncResult(task_id)
    slog("task_status_checked", task_id=task_id, state=result.state)
    if result.state == "SUCCESS":
        task_doc = task_result_repo.get_task_by_task_id(task_id=task_id)
        if task_doc:
            task_result_repo.upsert_task_result(
                tenant_id=task_doc["tenant_id"],
                task_id=task_id,
                status="SUCCESS",
                result_payload=result.result if isinstance(result.result, dict) else {"value": result.result},
            )
        return result.result
    if result.state == "FAILURE":
        task_doc = task_result_repo.get_task_by_task_id(task_id=task_id)
        if task_doc:
            error_message = str(result.result)
            task_result_repo.upsert_task_result(
                tenant_id=task_doc["tenant_id"],
                task_id=task_id,
                status="FAILURE",
                error=error_message,
            )
            audit_repo.log_event(
                tenant_id=task_doc["tenant_id"],
                actor_id=task_doc.get("created_by", "system"),
                action="task.failure",
                resource_type="task",
                resource_id=task_id,
                result="failure",
                request_id=task_doc.get("request_id", "n/a"),
                details={"error": error_message},
            )
    elif result.state in {"STARTED", "RETRY", "PENDING"}:
        task_result_repo.update_status_by_task_id(task_id=task_id, status=result.state)
    return {"status": result.state}


def _quota_for_tier(plan_tier: str) -> int:
    limits = {
        "standard": int(os.getenv("TENANT_QUOTA_STANDARD", "2")),
        "pro": int(os.getenv("TENANT_QUOTA_PRO", "5")),
        "enterprise": int(os.getenv("TENANT_QUOTA_ENTERPRISE", "10")),
    }
    return limits.get(plan_tier, limits["standard"])


@app.get("/tasks/{task_id}", response_model=dict)
def get_task_result(
    task_id: str,
    context: RequestContext = Depends(require_request_context),
):
    require_roles(context, {"tenant_admin", "ml_operator", "viewer"})
    slog(
        "task_result_requested",
        tenant_id=context.tenant_id,
        actor_id=context.actor_id,
        request_id=context.request_id,
        task_id=task_id,
    )
    task_doc = task_result_repo.get_task_for_tenant(tenant_id=context.tenant_id, task_id=task_id)
    if not task_doc:
        raise HTTPException(status_code=404, detail="Task not found")

    result = AsyncResult(task_id)
    result_data = {
        "task_id": task_id,
        "status": task_doc.get("status", result.state),
    }

    if result.state == "SUCCESS":
        result_data["result"] = result.result
    elif result.state == "FAILURE":
        result_data["result"] = str(result.result)

    audit_repo.log_event(
        tenant_id=context.tenant_id,
        actor_id=context.actor_id,
        action="task.result_read",
        resource_type="task",
        resource_id=task_id,
        result="success",
        request_id=context.request_id,
        details={"status": result_data["status"]},
    )

    return build_success_response(context, result_data)


@app.get("/dashboard/summary", response_model=dict)
def get_dashboard_summary(
    context: RequestContext = Depends(require_request_context),
):
    require_roles(context, {"tenant_admin", "ml_operator", "viewer"})
    metrics = task_result_repo.summarize_task_metrics_for_tenant(tenant_id=context.tenant_id)
    recent_tasks = task_result_repo.list_recent_tasks_for_tenant(tenant_id=context.tenant_id, limit=20)
    active_count = task_result_repo.count_active_tasks_for_tenant(tenant_id=context.tenant_id)
    data = {
        "metrics": metrics,
        "active_tasks": active_count,
        "recent_tasks": recent_tasks,
    }
    slog(
        "dashboard_summary_requested",
        tenant_id=context.tenant_id,
        actor_id=context.actor_id,
        request_id=context.request_id,
    )
    return build_success_response(context, data)


@app.get("/operations/audit-events", response_model=dict)
def get_audit_events(
    limit: int = 100,
    action: Optional[str] = None,
    context: RequestContext = Depends(require_request_context),
):
    require_roles(context, {"tenant_admin", "ml_operator", "viewer"})
    safe_limit = min(max(limit, 1), 500)
    events = audit_repo.list_events_for_tenant(
        tenant_id=context.tenant_id,
        limit=safe_limit,
        action=action,
    )
    slog(
        "audit_events_requested",
        tenant_id=context.tenant_id,
        actor_id=context.actor_id,
        request_id=context.request_id,
        limit=safe_limit,
        action=action,
    )
    return build_success_response(
        context,
        {
            "count": len(events),
            "events": events,
        },
    )


@app.get("/operations/quota", response_model=dict)
def get_quota_status(
    context: RequestContext = Depends(require_request_context),
):
    require_roles(context, {"tenant_admin", "ml_operator", "viewer"})
    max_concurrency = _quota_for_tier(context.plan_tier)
    active_count = task_result_repo.count_active_tasks_for_tenant(tenant_id=context.tenant_id)
    data = {
        "plan_tier": context.plan_tier,
        "active_count": active_count,
        "max_concurrency": max_concurrency,
        "remaining_capacity": max(0, max_concurrency - active_count),
    }
    slog(
        "quota_status_requested",
        tenant_id=context.tenant_id,
        actor_id=context.actor_id,
        request_id=context.request_id,
    )
    return build_success_response(context, data)


@app.get("/tasks/{task_id}/causal-report", response_model=dict)
def get_causal_report(
    task_id: str,
    context: RequestContext = Depends(require_request_context),
):
    require_roles(context, {"tenant_admin", "ml_operator", "viewer"})
    task_doc = task_result_repo.get_task_for_tenant(tenant_id=context.tenant_id, task_id=task_id)
    if not task_doc:
        raise HTTPException(status_code=404, detail="Task not found")

    report = causal_report_repo.get_report_by_task_for_tenant(tenant_id=context.tenant_id, task_id=task_id)
    if not report:
        raise HTTPException(status_code=404, detail="Causal report not found")

    slog(
        "causal_report_requested",
        tenant_id=context.tenant_id,
        actor_id=context.actor_id,
        request_id=context.request_id,
        task_id=task_id,
    )
    audit_repo.log_event(
        tenant_id=context.tenant_id,
        actor_id=context.actor_id,
        action="causal_report.read",
        resource_type="causal_report",
        resource_id=report.get("analysis_id", task_id),
        result="success",
        request_id=context.request_id,
        details={"task_id": task_id},
    )
    return build_success_response(context, {"task_id": task_id, "causal_report": report})


@app.get("/tasks/{task_id}/action-recommendation", response_model=dict)
def get_action_recommendation(
    task_id: str,
    context: RequestContext = Depends(require_request_context),
):
    require_roles(context, {"tenant_admin", "ml_operator", "viewer"})
    task_doc = task_result_repo.get_task_for_tenant(tenant_id=context.tenant_id, task_id=task_id)
    if not task_doc:
        raise HTTPException(status_code=404, detail="Task not found")

    recommendation = action_recommendation_repo.get_recommendation_by_task_for_tenant(
        tenant_id=context.tenant_id,
        task_id=task_id,
    )
    if not recommendation:
        raise HTTPException(status_code=404, detail="Action recommendation not found")

    slog(
        "action_recommendation_requested",
        tenant_id=context.tenant_id,
        actor_id=context.actor_id,
        request_id=context.request_id,
        task_id=task_id,
    )
    audit_repo.log_event(
        tenant_id=context.tenant_id,
        actor_id=context.actor_id,
        action="action_recommendation.read",
        resource_type="action_recommendation",
        resource_id=recommendation.get("recommendation_id", task_id),
        result="success",
        request_id=context.request_id,
        details={"task_id": task_id},
    )
    return build_success_response(
        context,
        {"task_id": task_id, "action_recommendation": recommendation},
    )


@app.get("/tasks/{task_id}/explanations", response_model=dict)
def get_task_explanations(
    task_id: str,
    context: RequestContext = Depends(require_request_context),
):
    """
    Retrieve SHAP/LIME explanations for a task's anomaly detection results.

    Returns feature importance, SHAP values, and instance-level explanations.
    """
    require_roles(context, {"tenant_admin", "ml_operator", "viewer"})
    task_doc = task_result_repo.get_task_for_tenant(tenant_id=context.tenant_id, task_id=task_id)
    if not task_doc:
        raise HTTPException(status_code=404, detail="Task not found")

    # Extract SHAP analysis from task result if available
    result_payload = task_doc.get("result_payload", {})
    shap_analysis = result_payload.get("shap_analysis")

    if not shap_analysis:
        raise HTTPException(
            status_code=404,
            detail="SHAP explanations not available for this task. Try requesting a new analysis.",
        )

    slog(
        "task_explanations_requested",
        tenant_id=context.tenant_id,
        actor_id=context.actor_id,
        request_id=context.request_id,
        task_id=task_id,
    )
    audit_repo.log_event(
        tenant_id=context.tenant_id,
        actor_id=context.actor_id,
        action="explanations.read",
        resource_type="explanations",
        resource_id=task_id,
        result="success",
        request_id=context.request_id,
        details={"task_id": task_id, "analysis_type": "shap"},
    )

    # Extract key fields for response
    explanation_response = {
        "task_id": task_id,
        "algorithm": shap_analysis.get("algorithm"),
        "method": shap_analysis.get("method"),
        "feature_importance": shap_analysis.get("feature_importance", {}),
        "outlier_explanations": shap_analysis.get("outlier_explanations", {}),
        "n_samples_analyzed": shap_analysis.get("n_samples_analyzed"),
        "n_outliers_analyzed": shap_analysis.get("n_outliers_analyzed"),
    }

    return build_success_response(context, explanation_response)


@app.post("/tasks/{task_id}/request-explanation", response_model=dict)
def request_task_explanation(
    task_id: str,
    request: Optional[Dict[str, Any]] = None,
    context: RequestContext = Depends(require_request_context),
):
    """
    Request SHAP/LIME explanation for an existing task result.

    This endpoint triggers a background job to calculate explanations if not already done.
    """
    require_roles(context, {"tenant_admin", "ml_operator"})
    task_doc = task_result_repo.get_task_for_tenant(tenant_id=context.tenant_id, task_id=task_id)
    if not task_doc:
        raise HTTPException(status_code=404, detail="Task not found")

    if task_doc.get("status") != "SUCCESS":
        raise HTTPException(
            status_code=400,
            detail="Task must be in SUCCESS status to request explanations",
        )

    slog(
        "explanation_request_submitted",
        tenant_id=context.tenant_id,
        actor_id=context.actor_id,
        request_id=context.request_id,
        task_id=task_id,
    )
    audit_repo.log_event(
        tenant_id=context.tenant_id,
        actor_id=context.actor_id,
        action="explanations.request",
        resource_type="explanations",
        resource_id=task_id,
        result="pending",
        request_id=context.request_id,
        details={"task_id": task_id},
    )

    return build_success_response(
        context,
        {
            "task_id": task_id,
            "message": "Explanation request submitted. Use GET /tasks/{task_id}/explanations to retrieve results.",
            "status": "pending",
        },
    )

