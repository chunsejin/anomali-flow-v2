from typing import Dict

from celery.result import AsyncResult
from fastapi import BackgroundTasks, Depends, FastAPI
from pydantic import BaseModel
from pymongo import MongoClient

import celeryconfig
from auth import RequestContext, require_request_context, require_roles
from worker import run_categorical_workflow, run_timeseries_workflow


app = FastAPI()

client = MongoClient("mongo", 27017)
db = client.celery_results
collection = db.results


class TaskRequest(BaseModel):
    df: Dict
    algorithm: str
    params: dict


@app.post("/tasks", response_model=dict)
def run_task(
    request: TaskRequest,
    background_tasks: BackgroundTasks,
    context: RequestContext = Depends(require_request_context),
):
    require_roles(context, {"tenant_admin", "ml_operator"})

    if request.algorithm in ["DBSCAN", "KMeans"]:
        task = run_timeseries_workflow.delay(request.df, request.algorithm, request.params)
    else:
        task = run_categorical_workflow.delay(request.df, request.algorithm, request.params)

    background_tasks.add_task(check_task_status, task.id)
    return {
        "task_id": task.id,
        "tenant_id": context.tenant_id,
        "submitted_by": context.actor_id,
        "request_id": context.request_id,
    }


def check_task_status(task_id: str):
    result = AsyncResult(task_id)
    if result.state == "SUCCESS":
        collection.insert_one({"task_id": task_id, "result": result.result})
        return result.result
    return {"status": result.state}


@app.get("/tasks/{task_id}", response_model=dict)
def get_task_result(
    task_id: str,
    context: RequestContext = Depends(require_request_context),
):
    require_roles(context, {"tenant_admin", "ml_operator", "viewer"})

    result = AsyncResult(task_id)
    response = {
        "status": result.state,
        "tenant_id": context.tenant_id,
        "request_id": context.request_id,
    }

    if result.state == "SUCCESS":
        response["result"] = result.result
    elif result.state == "FAILURE":
        response["result"] = str(result.result)

    return response
