from typing import Any, Dict, Optional
from uuid import uuid4

from celery.result import AsyncResult
from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

import celeryconfig
from auth import RequestContext, require_request_context, require_roles
from repositories import AuditRepository, TaskResultRepository
from worker import run_categorical_workflow, run_timeseries_workflow


app = FastAPI()
task_result_repo = TaskResultRepository()
audit_repo = AuditRepository()
POLICY_VERSION = "v1"


class TaskRequest(BaseModel):
    df: Dict
    algorithm: str
    params: dict


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

    if request.algorithm in ["DBSCAN", "KMeans"]:
        task = run_timeseries_workflow.delay(
            request.df,
            request.algorithm,
            request.params,
            tenant_context,
        )
    else:
        task = run_categorical_workflow.delay(
            request.df,
            request.algorithm,
            request.params,
            tenant_context,
        )

    task_result_repo.create_submitted_task(
        tenant_id=context.tenant_id,
        task_id=task.id,
        algorithm=request.algorithm,
        params=request.params,
        created_by=context.actor_id,
        request_id=context.request_id,
        plan_tier=context.plan_tier,
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


@app.get("/tasks/{task_id}", response_model=dict)
def get_task_result(
    task_id: str,
    context: RequestContext = Depends(require_request_context),
):
    require_roles(context, {"tenant_admin", "ml_operator", "viewer"})
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
