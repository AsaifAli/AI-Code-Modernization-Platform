"""Small context-local progress bridge from Agno workflow execution to task API."""
from __future__ import annotations

import json
from contextvars import ContextVar
from typing import Any

from app.infrastructure.repositories.task_repository import update_task

_task_id: ContextVar[str | None] = ContextVar("migration_task_id", default=None)


def bind_task(task_id: str) -> None:
    _task_id.set(task_id)


def publish_progress(stage: str, percent: int, message: str, *, plan: list[dict[str, Any]] | None = None) -> None:
    task_id = _task_id.get()
    if not task_id:
        return
    payload = {"kind": "progress", "stage": stage, "percent": max(0, min(100, int(percent))), "message": message}
    if plan is not None:
        payload["plan"] = plan
    try:
        update_task(task_id, result=json.dumps(payload))
    except Exception:
        pass
