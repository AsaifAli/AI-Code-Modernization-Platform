"""Persists task status in Postgres when configured.

The status record survives a service restart, but the process-local background
execution itself is not durable; interrupted work is marked failed at startup.
A queue/worker system is the next production-hardening step."""
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.infrastructure.db.db_connection import engine
from app.infrastructure.db.models import AgentTask

logger = logging.getLogger(__name__)

_fallback_tasks: Dict[str, dict] = {}


def _to_dict(row: AgentTask) -> dict:
    return {
        "status": row.status,
        "result": row.result,
        "error": row.error,
        "started_at": row.started_at.isoformat() if row.started_at else None,
        "completed_at": row.completed_at.isoformat() if row.completed_at else None,
        "user_id": row.user_id,
    }


def create_task(task_id: str, user_id: str, status: str) -> None:
    if engine is None:
        _fallback_tasks[task_id] = {
            "status": status, "result": None, "error": None,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "completed_at": None, "user_id": str(user_id),
        }
        return
    try:
        with Session(engine) as session:
            session.add(AgentTask(
                task_id=task_id,
                user_id=str(user_id),
                status=status,
                started_at=datetime.now(timezone.utc),
            ))
            session.commit()
    except Exception:
        logger.exception("Failed to persist new task '%s'; falling back to in-memory only", task_id)
        _fallback_tasks[task_id] = {
            "status": status, "result": None, "error": None,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "completed_at": None, "user_id": str(user_id),
        }


def update_task(
    task_id: str,
    status: Optional[str] = None,
    result: Optional[str] = None,
    error: Optional[str] = None,
    mark_completed: bool = False,
) -> None:
    if engine is None:
        row = _fallback_tasks.get(task_id)
        if row is None:
            return
        if status is not None:
            row["status"] = status
        if result is not None:
            row["result"] = result
        if error is not None:
            row["error"] = error
        if mark_completed:
            row["completed_at"] = datetime.now(timezone.utc).isoformat()
        return
    try:
        with Session(engine) as session:
            row = session.get(AgentTask, task_id)
            if row is None:
                logger.warning("update_task: task '%s' not found in DB", task_id)
                return
            if status is not None:
                row.status = status
            if result is not None:
                row.result = result
            if error is not None:
                row.error = error
            if mark_completed:
                row.completed_at = datetime.now(timezone.utc)
            session.commit()
    except Exception:
        logger.exception("Failed to update task '%s'", task_id)


def get_task(task_id: str) -> Optional[dict]:
    if engine is None:
        return _fallback_tasks.get(task_id)
    try:
        with Session(engine) as session:
            row = session.get(AgentTask, task_id)
            return _to_dict(row) if row else None
    except Exception:
        logger.exception("Failed to fetch task '%s'", task_id)
        return None


def mark_orphaned_running_tasks_as_failed() -> int:
    """Call once at startup: any task still 'running' means agent_service died
    mid-migration last time — the background asyncio task is gone, so it will
    never update again. Flip it to failed instead of leaving it stuck forever."""
    if engine is None:
        count = 0
        for row in _fallback_tasks.values():
            if row.get("status") == "running":
                row["status"] = "failed"
                row["error"] = "Interrupted by agent_service restart"
                row["completed_at"] = datetime.now(timezone.utc).isoformat()
                count += 1
        return count
    try:
        with Session(engine) as session:
            rows = session.query(AgentTask).filter(AgentTask.status == "running").all()
            for row in rows:
                row.status = "failed"
                row.error = "Interrupted by agent_service restart"
                row.completed_at = datetime.now(timezone.utc)
            session.commit()
            return len(rows)
    except Exception:
        logger.exception("Failed to sweep orphaned running tasks")
        return 0
