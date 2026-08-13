"""
Agent orchestrator: sets context and runs the migration workflow (latest application logic).
"""
import logging
import asyncio
import json
import uuid
from pathlib import Path
from app.infrastructure.utils.user_context import current_user
from app.infrastructure.workflows.migration_workflow import migration_workflow
from app.infrastructure.repositories.migration_data_repository import (
    fetch_migration_data,
    upsert_migration_data,
)
from app.application.agents.knowledge_base.knowledge_base_agent import init_knowledge_bases
from app.infrastructure.utils.Constants.migration_workflow import MigrationWorkflowStrings
from app.infrastructure.utils.Constants.app_constants import AgentConstants, PathConstants
from app.infrastructure.utils.migration_context import (
    migration_id_ctx,
    migration_name_ctx,
    migration_path_ctx,
    source_path_ctx,
    target_path_ctx,
    target_language_ctx,
    description_ctx,
    target_framework_ctx,
    target_architecture_ctx,
    is_frontend_ctx,
    target_frontend_ctx,
    target_frontend_architecture_ctx,
)
from app.application.agents.utility_agent import detect_target_stack_from_description
from app.infrastructure.utils.token_tracker import ingest_workflow_response  # ← NEW
from app.infrastructure.utils.migration_packager import package_migrated_code
from app.infrastructure.utils.task_progress import bind_task, publish_progress
from app.infrastructure.utils.file_utils import get_migration_directory

logger = logging.getLogger(__name__)


def _workflow_result_payload(workflow_output) -> dict:
    """Convert Agno's response objects into a stable task/API outcome.

    Depending on whether a workflow was streamed or stopped early, Agno can
    return the final workflow response, a step output, or a response wrapper.
    Do not rely on one specific response shape for the release decision.
    """
    seen: set[int] = set()

    def visit(value):
        if value is None or id(value) in seen:
            return None
        seen.add(id(value))
        if isinstance(value, str):
            try:
                return visit(json.loads(value))
            except (TypeError, ValueError):
                return None
        if isinstance(value, dict):
            gate = value.get("quality_gate")
            if isinstance(gate, dict):
                return gate
            for child in value.values():
                found = visit(child)
                if found is not None:
                    return found
            return None
        if isinstance(value, (list, tuple)):
            for child in value:
                found = visit(child)
                if found is not None:
                    return found
            return None
        for attr in ("step_results", "content", "output", "response", "result"):
            found = visit(getattr(value, attr, None))
            if found is not None:
                return found
        return None

    quality_gate = visit(workflow_output)
    release_ready = bool((quality_gate or {}).get("release_ready"))
    message = (
        (quality_gate or {}).get("message")
        or ("Migration passed the post-migration release gate." if release_ready
            else "Migration did not pass the post-migration release gate; no release ZIP was created.")
    )
    return {
        "status": "ready" if release_ready else "blocked",
        "release_ready": release_ready,
        "quality_gate": quality_gate,
        "message": message,
    }


class WorkflowOrchestrator:
    """
    AI-driven orchestrator that delegates to the Migration Workflow
    (scan → analyse → build KB → convert). Multi-user safe via context vars.
    """

    def __init__(self):
        self.workflow = migration_workflow

    async def run_workflow(
        self,
        source_path: str,
        migration_name: str,
        target: str | None,
        description: str | None,
        target_path: str,
        github_token: str = "",
        user_id: str = None,
        task_id: str | None = None,
        framework: str = None,
        architecture: str = None,
        build_tool: str = None,
        database: str = None,
    ) -> str:
        """
        Fully agentic orchestration (MULTI-USER SAFE).
        Sets per-request context then runs the workflow.
        """
        user = current_user.get()
        if task_id:
            bind_task(task_id)
        migration_name_ctx.set(migration_name)
        source_path = str(Path(source_path).resolve())
        source_path_ctx.set(source_path)

        if not user_id:
            user_id = user.id

        migration_working_dir = (
            Path(PathConstants.TEMP_DIR)
            / str(user_id)
            / migration_name
            / MigrationWorkflowStrings.DEST_FOLDER
            / migration_name
        )
        migration_working_dir.mkdir(parents=True, exist_ok=True)
        migration_path_ctx.set(str(migration_working_dir.absolute()))

        logger.info("Migration working directory (dest): %s", migration_working_dir)
        description_value = (description or "").strip()
        description_ctx.set(description_value)

        detected_stack = detect_target_stack_from_description(description_value)
        target_language = (
            (target or "").strip().lower()
            or str(detected_stack.get(AgentConstants.TARGET_LANGUAGE) or "").strip().lower()
            or AgentConstants.DEFAULT_TARGET_LANGUAGE
        )
        target_framework = (
            str(detected_stack.get(AgentConstants.TARGET_FRAMEWORK) or "").strip().lower()
            or AgentConstants.DEFAULT_TARGET_FRAMEWORK
        )
        target_architecture = (
            str(detected_stack.get(AgentConstants.TARGET_ARCHITECTURE) or "").strip().lower()
            or AgentConstants.DEFAULT_TARGET_ARCHITECTURE
        )
        is_frontend = bool(detected_stack.get(AgentConstants.IS_FRONTEND, False))
        target_frontend = str(detected_stack.get(AgentConstants.TARGET_FRONTEND) or "").strip().lower()
        target_frontend_architecture = str(
            detected_stack.get(AgentConstants.TARGET_FRONTEND_ARCHITECTURE) or ""
        ).strip().lower()
        if is_frontend and not target_frontend:
            target_frontend = AgentConstants.DEFAULT_TARGET_FRONTEND

        target_language_ctx.set(target_language)
        target_framework_ctx.set(target_framework)
        target_architecture_ctx.set(target_architecture)
        is_frontend_ctx.set(is_frontend)
        target_frontend_ctx.set(target_frontend)
        target_frontend_architecture_ctx.set(target_frontend_architecture)

        if target_path:
            target_path_resolved = Path(target_path).resolve()
            if target_path_resolved.exists() and target_path_resolved.is_dir():
                try:
                    if any(target_path_resolved.iterdir()):
                        target_path_ctx.set(str(target_path_resolved))
                        logger.info("Target project path set in context: %s", target_path_ctx.get())
                    else:
                        target_path_ctx.set(None)
                        logger.info("Target directory is empty → target analysis will be skipped")
                except Exception as e:
                    logger.warning("Error checking target directory: %s", e)
                    target_path_ctx.set(None)
            else:
                target_path_ctx.set(None)
                logger.warning("Target path does not exist or is not a directory: %s", target_path)
        else:
            target_path_ctx.set(None)
            logger.info("No target_path provided → target analysis will be skipped")

        logger.info("Migration Path (working dir): %s", migration_path_ctx.get())
        logger.info("Migration Name: %s", migration_name)
        logger.info("Source Path: %s", source_path)
        logger.info("Description: %s", description_value or None)
        logger.info("Target Language: %s", target_language)
        logger.info("Target Framework: %s", target_framework)
        logger.info("Target Architecture: %s", target_architecture)
        logger.info("Is Frontend: %s", is_frontend)
        logger.info("Target Frontend: %s", target_frontend or "None")

        # Ensure migration_data has one entry per migration_name.
        # If already present, skip insert to avoid duplicate writes across reruns.
        try:
            existing_row = fetch_migration_data(
                migration_name=migration_name,
                user_id=user.id,
            )
            if existing_row:
                logger.info(
                    "migration_data entry already exists for migration_name=%s (id=%s). Skipping insert.",
                    migration_name,
                    existing_row.get("id"),
                )
                migration_id_ctx.set(existing_row.get("id"))
            else:
                row_id = upsert_migration_data(
                    migration_name=migration_name,
                    user_id=user.id,
                    created_by=user.id,
                    updated_by=user.id,
                )
                if row_id is not None:
                    logger.info(
                        "Created migration_data entry for migration_name=%s (id=%s).",
                        migration_name,
                        row_id,
                    )
                    migration_id_ctx.set(row_id)
                else:
                    logger.warning(
                        "Failed to create migration_data entry for migration_name=%s.",
                        migration_name,
                    )
        except Exception as exc:
            logger.warning("migration_data ensure step failed: %s", exc)
        
        init_knowledge_bases()

        plan_names = [
            "Scan source", "Verify scan", "Build knowledge base", "Plan migration",
            "Verify plan", "Convert code", "Post-migration engineering",
        ]
        plan = [{"name": n, "status": "pending", "percent": int((i / len(plan_names)) * 100)} for i, n in enumerate(plan_names)]
        publish_progress("planning", 1, "Migration workflow started", plan=plan)

        def _run_streaming():
            stream = self.workflow.run(
                input=source_path_ctx.get(),
                session_id=str(uuid.uuid4()),
                debug_mode=True,
                show_step_details=True,
                stream=True,
                stream_events=True,
                stream_executor_events=False,
                # Agno is the canonical execution event source; task_progress
                # persists a compact snapshot for the REST/UI client.
                store_events=True,
            )
            final_output = None
            # Only these outer workflow names may update the seven-stage UI.
            # Nested scanner/planner events must not be mistaken for later
            # stages, otherwise the progress bar and chips diverge.
            step_lookup = {
                "scan_workflow": 0,
                "verify scan output": 1,
                "kb_workflow": 2,
                "plan_workflow": 3,
                "verify plan complete": 4,
                "convert_workflow": 5,
                "post_migration_workflow": 6,
            }
            for event in stream:
                event_name = str(getattr(event, "event", "") or type(event).__name__).lower()
                step_name = str(getattr(event, "step_name", "") or getattr(event, "step", "") or "").strip()
                if "stepstarted" in event_name or "step_started" in event_name:
                    idx = step_lookup.get(step_name.lower(), None)
                    if idx is None:
                        continue
                    for j, item in enumerate(plan):
                        item["status"] = "complete" if j < idx else ("running" if j == idx else "pending")
                    publish_progress("workflow", max(1, int(idx / len(plan) * 100)), f"Running: {step_name or plan[idx]['name']}", plan=plan)
                elif "stepcompleted" in event_name or "step_completed" in event_name:
                    idx = step_lookup.get(step_name.lower(), None)
                    if idx is None:
                        continue
                    plan[idx]["status"] = "complete"
                    publish_progress("workflow", int(((idx + 1) / len(plan)) * 100), f"Completed: {step_name or plan[idx]['name']}", plan=plan)
                elif hasattr(event, "content") and getattr(event, "content", None):
                    final_output = event
            return getattr(self.workflow, "run_response", None) or final_output

        result = await asyncio.to_thread(_run_streaming)
        for item in plan:
            if item["status"] != "complete":
                item["status"] = "complete"
        publish_progress("completed", 100, "Workflow execution complete", plan=plan)

        # ── Harvest Agno-native step metrics and persist to DB ─────────────
        ingest_workflow_response(result)
        # ──────────────────────────────────────────────────────────────────

        # ── Demo artifact packaging ─────────────────────────────────────────
        # The post-migration quality gate still controls release readiness, but
        # portfolio/demo users should be able to inspect the generated code even
        # when that gate is red. Packaging is filesystem-only and does not change
        # the quality decision. The UI labels a red-gate ZIP as not release-ready.
        workflow_outcome = _workflow_result_payload(result)

        try:
            migration_dir = get_migration_directory(
                migration_name=migration_name_ctx.get(""),
                source_path=source_path_ctx.get(""),
            )
            package_result = package_migrated_code(migration_dir, migration_name_ctx.get(""))
            if workflow_outcome.get("release_ready"):
                logger.info("Release package created after green post-migration quality gate: %s", package_result)
            else:
                logger.warning(
                    "Demo artifact packaged despite red post-migration quality gate for '%s': %s",
                    migration_name_ctx.get(""),
                    package_result,
                )
        except Exception:
            logger.exception("Packaging converted output failed for migration '%s'", migration_name_ctx.get(""))
        # ──────────────────────────────────────────────────────────────────

        if workflow_outcome["release_ready"]:
            logger.info(AgentConstants.TEAM_FINISHED_LOG, workflow_outcome["message"])
        else:
            logger.warning("Migration workflow finished with a blocked release gate: %s", workflow_outcome["message"])
        return json.dumps(workflow_outcome, default=str)
