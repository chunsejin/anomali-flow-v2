from __future__ import annotations

from datetime import datetime, timezone
from functools import lru_cache
from typing import Any, Optional

from pymongo import ASCENDING, DESCENDING, MongoClient


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@lru_cache
def get_mongo_client() -> MongoClient:
    return MongoClient("mongo", 27017)


class TaskResultRepository:
    def __init__(self) -> None:
        db = get_mongo_client().celery_results
        self._collection = db.task_results
        self._collection.create_index(
            [("tenant_id", ASCENDING), ("task_id", ASCENDING)],
            unique=True,
            name="tenant_task_unique",
        )
        self._collection.create_index(
            [("tenant_id", ASCENDING), ("created_at", DESCENDING)],
            name="tenant_created_at_desc",
        )
        self._collection.create_index(
            [("tenant_id", ASCENDING), ("idempotency_key", ASCENDING)],
            unique=True,
            sparse=True,
            name="tenant_idempotency_unique",
        )

    def create_submitted_task(
        self,
        *,
        tenant_id: str,
        task_id: str,
        algorithm: str,
        params: dict[str, Any],
        created_by: str,
        request_id: str,
        plan_tier: str,
        retention_class: str = "standard",
    ) -> None:
        now = _utc_now()
        doc = {
            "tenant_id": tenant_id,
            "task_id": task_id,
            "status": "PENDING",
            "algorithm": algorithm,
            "params": params,
            "created_by": created_by,
            "created_at": now,
            "updated_at": now,
            "retention_class": retention_class,
            "request_id": request_id,
            "plan_tier": plan_tier,
        }
        self._collection.update_one(
            {"tenant_id": tenant_id, "task_id": task_id},
            {"$setOnInsert": doc},
            upsert=True,
        )

    def upsert_task_result(
        self,
        *,
        tenant_id: str,
        task_id: str,
        status: str,
        idempotency_key: Optional[str] = None,
        algorithm: Optional[str] = None,
        params: Optional[dict[str, Any]] = None,
        created_by: Optional[str] = None,
        request_id: Optional[str] = None,
        plan_tier: Optional[str] = None,
        result_payload: Optional[dict[str, Any]] = None,
        error: Optional[str] = None,
    ) -> None:
        now = _utc_now()
        set_fields: dict[str, Any] = {
            "status": status,
            "updated_at": now,
        }
        if request_id is not None:
            set_fields["request_id"] = request_id
        if plan_tier is not None:
            set_fields["plan_tier"] = plan_tier
        if algorithm is not None:
            set_fields["algorithm"] = algorithm
        if idempotency_key is not None:
            set_fields["idempotency_key"] = idempotency_key
        if params is not None:
            set_fields["params"] = params
        if created_by is not None:
            set_fields["created_by"] = created_by
        if result_payload is not None:
            set_fields["result_payload"] = result_payload
        if error is not None:
            set_fields["error"] = error

        self._collection.update_one(
            {"tenant_id": tenant_id, "task_id": task_id},
            {
                "$set": set_fields,
                "$setOnInsert": {
                    "tenant_id": tenant_id,
                    "task_id": task_id,
                    "created_at": now,
                    "retention_class": "standard",
                },
            },
            upsert=True,
        )

    def update_status_by_task_id(self, *, task_id: str, status: str, error: Optional[str] = None) -> None:
        set_fields: dict[str, Any] = {"status": status, "updated_at": _utc_now()}
        if error is not None:
            set_fields["error"] = error
        self._collection.update_one({"task_id": task_id}, {"$set": set_fields})

    def get_task_for_tenant(self, *, tenant_id: str, task_id: str) -> Optional[dict[str, Any]]:
        return self._collection.find_one({"tenant_id": tenant_id, "task_id": task_id}, {"_id": 0})

    def get_task_by_task_id(self, *, task_id: str) -> Optional[dict[str, Any]]:
        return self._collection.find_one({"task_id": task_id}, {"_id": 0})

    def get_task_by_idempotency(self, *, tenant_id: str, idempotency_key: str) -> Optional[dict[str, Any]]:
        return self._collection.find_one(
            {"tenant_id": tenant_id, "idempotency_key": idempotency_key},
            {"_id": 0},
        )

    def count_active_tasks_for_tenant(self, *, tenant_id: str) -> int:
        return self._collection.count_documents(
            {"tenant_id": tenant_id, "status": {"$in": ["PENDING", "STARTED", "RETRY"]}}
        )


class AuditRepository:
    def __init__(self) -> None:
        db = get_mongo_client().celery_results
        self._collection = db.audit_events
        self._collection.create_index(
            [("tenant_id", ASCENDING), ("timestamp", DESCENDING)],
            name="tenant_timestamp_desc",
        )
        self._collection.create_index(
            [("tenant_id", ASCENDING), ("request_id", ASCENDING)],
            name="tenant_request",
        )

    def log_event(
        self,
        *,
        tenant_id: str,
        actor_id: str,
        action: str,
        resource_type: str,
        resource_id: str,
        result: str,
        request_id: str,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        self._collection.insert_one(
            {
                "tenant_id": tenant_id,
                "actor_id": actor_id,
                "action": action,
                "resource_type": resource_type,
                "resource_id": resource_id,
                "result": result,
                "request_id": request_id,
                "details": details or {},
                "timestamp": _utc_now(),
            }
        )
