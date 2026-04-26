from __future__ import annotations

import os
import time
import uuid
from typing import Any

import requests


API_BASE_URL = os.getenv("ANOMALIFLOW_API_BASE_URL", "http://localhost:8000").rstrip("/")
DEFAULT_TIMEOUT_SEC = int(os.getenv("ANOMALIFLOW_API_TIMEOUT_SEC", "120"))
POLL_INTERVAL_SEC = float(os.getenv("ANOMALIFLOW_API_POLL_INTERVAL_SEC", "1.5"))


def _build_headers(token: str | None, request_id: str) -> dict[str, str]:
    headers = {
        "Content-Type": "application/json",
        "X-Request-Id": request_id,
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def submit_task(
    *,
    df_records: list[dict[str, Any]],
    algorithm: str,
    params: dict[str, Any],
    token: str | None,
    request_id: str | None = None,
) -> tuple[str, str]:
    trace_id = request_id or str(uuid.uuid4())
    headers = _build_headers(token, trace_id)
    payload = {
        "df": df_records,
        "algorithm": algorithm,
        "params": params,
    }
    resp = requests.post(
        f"{API_BASE_URL}/tasks",
        json=payload,
        headers=headers,
        timeout=30,
    )
    resp.raise_for_status()
    body = resp.json()
    data = body.get("data", body)
    task_id = data.get("task_id")
    if not task_id:
        raise RuntimeError(f"Task submission response missing task_id: {body}")
    return task_id, trace_id


def fetch_task_result(*, task_id: str, token: str | None, request_id: str) -> dict[str, Any]:
    headers = _build_headers(token, request_id)
    resp = requests.get(
        f"{API_BASE_URL}/tasks/{task_id}",
        headers=headers,
        timeout=30,
    )
    resp.raise_for_status()
    body = resp.json()
    return body.get("data", body)


def wait_for_task_result(
    *,
    task_id: str,
    token: str | None,
    request_id: str,
    timeout_sec: int = DEFAULT_TIMEOUT_SEC,
) -> dict[str, Any]:
    started = time.time()
    while True:
        result = fetch_task_result(task_id=task_id, token=token, request_id=request_id)
        status = result.get("status")
        if status in {"SUCCESS", "FAILURE"}:
            return result
        if time.time() - started > timeout_sec:
            raise TimeoutError(f"Task {task_id} timed out after {timeout_sec}s")
        time.sleep(POLL_INTERVAL_SEC)


def fetch_dashboard_summary(*, token: str | None, request_id: str | None = None) -> dict[str, Any]:
    trace_id = request_id or str(uuid.uuid4())
    headers = _build_headers(token, trace_id)
    resp = requests.get(
        f"{API_BASE_URL}/dashboard/summary",
        headers=headers,
        timeout=30,
    )
    resp.raise_for_status()
    body = resp.json()
    return body.get("data", body)


def fetch_audit_events(
    *,
    token: str | None,
    limit: int = 100,
    action: str | None = None,
    request_id: str | None = None,
) -> dict[str, Any]:
    trace_id = request_id or str(uuid.uuid4())
    headers = _build_headers(token, trace_id)
    params: dict[str, Any] = {"limit": limit}
    if action:
        params["action"] = action
    resp = requests.get(
        f"{API_BASE_URL}/operations/audit-events",
        headers=headers,
        params=params,
        timeout=30,
    )
    resp.raise_for_status()
    body = resp.json()
    return body.get("data", body)


def fetch_quota_status(*, token: str | None, request_id: str | None = None) -> dict[str, Any]:
    trace_id = request_id or str(uuid.uuid4())
    headers = _build_headers(token, trace_id)
    resp = requests.get(
        f"{API_BASE_URL}/operations/quota",
        headers=headers,
        timeout=30,
    )
    resp.raise_for_status()
    body = resp.json()
    return body.get("data", body)


def fetch_causal_report(
    *,
    task_id: str,
    token: str | None,
    request_id: str | None = None,
) -> dict[str, Any]:
    trace_id = request_id or str(uuid.uuid4())
    headers = _build_headers(token, trace_id)
    resp = requests.get(
        f"{API_BASE_URL}/tasks/{task_id}/causal-report",
        headers=headers,
        timeout=30,
    )
    resp.raise_for_status()
    body = resp.json()
    return body.get("data", body)


def fetch_action_recommendation(
    *,
    task_id: str,
    token: str | None,
    request_id: str | None = None,
) -> dict[str, Any]:
    trace_id = request_id or str(uuid.uuid4())
    headers = _build_headers(token, trace_id)
    resp = requests.get(
        f"{API_BASE_URL}/tasks/{task_id}/action-recommendation",
        headers=headers,
        timeout=30,
    )
    resp.raise_for_status()
    body = resp.json()
    return body.get("data", body)
