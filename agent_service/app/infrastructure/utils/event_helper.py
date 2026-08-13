"""Migration event helper backed by Agno workflow streaming, not workflow event stream.

The migration workflow is the source of truth for execution events. These
small compatibility methods keep scanner/planning/conversion code decoupled
from transport concerns while emitting useful logs/task progress.
"""
from __future__ import annotations

import logging
from typing import Optional, Any

from app.infrastructure.utils.task_progress import publish_progress

logger = logging.getLogger(__name__)


class MigrationEventHelper:
    def __init__(self, agent_name: str = "", event_name: str = "") -> None:
        self.agent_name = agent_name
        self.event_name = event_name

    def _log(self, kind: str, message: str, **extra: Any) -> None:
        logger.info("[%s] %s: %s %s", self.agent_name or "migration", kind, message, extra or "")

    def send_step_start(self, step_id: str, step_name: str, user, msg_group_id: int):
        self._log("step_start", step_name, step_id=step_id)

    def send_step_description(self, step_id: str, step_name: str, user, msg_group_id: int):
        self._log("step_description", step_name, step_id=step_id)

    def send_step_log(self, step_id: str, log_message: str, user, msg_group_id: int):
        self._log("step_log", log_message, step_id=step_id)

    def send_step_error(self, step_id: str, step_name: str, error_message: str, user, msg_group_id: int):
        self._log("step_error", error_message, step_id=step_id, step_name=step_name)

    def send_step_result(self, step_id: str, step_name: str, result: Any, user, msg_group_id: int):
        self._log("step_result", step_name, step_id=step_id, result=result)

    def send_progress(self, percent: int, message: str, user, msg_group_id: int, plan_id: Optional[str] = ""):
        publish_progress("workflow", percent, message)
        self._log("progress", message, percent=percent, plan_id=plan_id)

    def send_workflow_complete(self, message: str, user, msg_group_id: int, event_name: str = None):
        publish_progress("completed", 100, message)
        self._log("workflow_complete", message)

    # Legacy callers may use these methods; they now only log because the
    # canonical UI stream comes from Agno Workflow.run(stream=True, stream_events=True).
    def send_substep_log(self, *args, **kwargs):
        self._log("substep_log", str(args[2] if len(args) > 2 else kwargs.get("log_message", "")))

    def send_substep_error(self, *args, **kwargs):
        self._log("substep_error", str(args[2] if len(args) > 2 else kwargs.get("error_message", "")))

    def send_substep_data(self, *args, **kwargs):
        self._log("substep_data", "artifact emitted")

    def send_step_data(self, *args, **kwargs):
        self._log("step_data", "artifact emitted")

