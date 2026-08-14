import json
import logging
import os
import shutil
import stat
import uuid
from datetime import datetime
from pathlib import Path
import re
from types import SimpleNamespace
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from agent_orchestrator import WorkflowOrchestrator
from app.domain.services.get_MigList_service import MigrationListService
from app.infrastructure.utils.Constants.agent_event import AgentEventMessages
from app.infrastructure.utils.Constants.app_constants import AgentConstants, PathConstants, ServiceConstants
from app.infrastructure.utils.Constants.migration_workflow import MigrationWorkflowStrings
from app.infrastructure.utils.auth_client import get_current_user_http as get_current_user
from app.infrastructure.repositories.migration_data_repository import fetch_migration_data, delete_migration_data
from app.infrastructure.repositories.task_repository import create_task, update_task, get_task
from app.infrastructure.utils.migration_context import (
    migration_id_ctx,
    migration_name_ctx,
    migration_path_ctx,
    migration_run_id_ctx,
)
from app.infrastructure.utils.user_context import current_user
from app.presentation.schemas.agent_api_schema import (
    ArchitectureRequest,
    ArchitectureResponse,
    ChatAskRequest,
    ChatAskResponse,
    MigrationReportRequest,
    MigrationShowcaseRequest,
    PostMigrationQualityRequest,
    PostMigrationRunRequest,
    RunTeamRequest,
    TaskAcceptedResponse,
    TaskStatusResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter()
_SAFE_MIGRATION_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._ -]{0,127}$")


def _validate_migration_name(name: str) -> str:
    """Reject path traversal and filesystem-ambiguous migration identifiers."""
    value = (name or "").strip()
    # Human-readable migration names may contain spaces. Keep path separators,
    # control characters, and traversal names forbidden.
    if not _SAFE_MIGRATION_NAME.fullmatch(value) or value in {".", ".."} or "  " in value:
        raise HTTPException(status_code=422, detail="Invalid migration_name")
    return value


def _resolve_tool_callable(maybe_callable: Any):
    for attr in ("entrypoint", "func", "_func"):
        candidate = getattr(maybe_callable, attr, None)
        if callable(candidate):
            return candidate
    if callable(maybe_callable):
        return maybe_callable
    raise TypeError(f"Object is not callable: {type(maybe_callable)!r}")


def _set_migration_context(migration_name: str, user: Any) -> Path:
    migration_name_setter = _resolve_tool_callable(migration_name_ctx.set)
    migration_name = _validate_migration_name(migration_name)
    migration_name_setter(migration_name)
    migration_run_id_ctx.set(str(uuid.uuid4()))
    # Bind migration_id from DB when available (same name may re-run; token rows use migration_run_id).
    try:
        uid = getattr(user, "id", None)
        if uid is not None:
            row = fetch_migration_data(
                migration_name=migration_name,
                user_id=int(uid),
            )
            if row and row.get("id") is not None:
                mid = int(row["id"])
                migration_id_setter = _resolve_tool_callable(migration_id_ctx.set)
                migration_id_setter(mid)
    except Exception as exc:
        logger.debug("Could not set migration_id from migration_data: %s", exc)
    # Use the same base as get_migration_directory / file_utils (cwd-independent absolute Temp).
    temp_base = Path(getattr(PathConstants, "TEMP_DIR", None) or Path(ServiceConstants.TEMP_FOLDER).resolve())
    migration_working_dir = (
        temp_base
        / str(getattr(user, "id", "") or "")
        / migration_name
        / MigrationWorkflowStrings.DEST_FOLDER
        / migration_name
    )
    migration_working_dir.mkdir(parents=True, exist_ok=True)
    migration_path_setter = _resolve_tool_callable(migration_path_ctx.set)
    migration_path_setter(str(migration_working_dir.resolve()))
    return migration_working_dir


def _migration_dest_dir(user_id: str, migration_name: str) -> Path:
    return (
        Path(PathConstants.TEMP_DIR)
        / str(user_id)
        / migration_name
        / "Dest"
        / migration_name
    )


def _remove_readonly(func, path, _excinfo):
    os.chmod(path, stat.S_IWRITE)
    func(path)


def _safe_extract_zip(upload: UploadFile, destination: Path) -> None:
    """Extract an uploaded ZIP safely into the API service filesystem."""
    destination.mkdir(parents=True, exist_ok=True)
    import io
    import zipfile

    payload = upload.file.read()
    if not payload:
        raise HTTPException(status_code=422, detail=f"Uploaded archive '{upload.filename or 'archive'}' is empty")
    try:
        with zipfile.ZipFile(io.BytesIO(payload)) as zf:
            base = destination.resolve()
            for member in zf.infolist():
                target = (destination / member.filename).resolve()
                if target != base and base not in target.parents:
                    raise HTTPException(status_code=422, detail="Archive contains an unsafe path")
            zf.extractall(destination)
    except zipfile.BadZipFile as exc:
        raise HTTPException(status_code=422, detail=f"Invalid ZIP archive: {exc}") from exc


@router.post("/v1/teams/upload")
async def upload_team_files(
    migration_name: str = Form(...),
    source_zip: UploadFile = File(...),
    target_zip: UploadFile | None = File(None),
    user=Depends(get_current_user),
):
    """Store uploads inside agent_service before queueing the background workflow.

    Render runs the UI and API as separate services, so their local filesystems
    are not shared. The returned paths therefore always belong to the API service.
    """
    current_user.set(user)
    migration_name = _validate_migration_name(migration_name)
    uid = str(getattr(user, "id", "") or "")
    work_id = uuid.uuid4().hex[:12]
    base = Path(PathConstants.TEMP_DIR) / uid / migration_name / "Uploads" / work_id
    source_dir = base / "source"
    _safe_extract_zip(source_zip, source_dir)
    target_path = None
    if target_zip is not None:
        target_dir = base / "target"
        _safe_extract_zip(target_zip, target_dir)
        target_path = str(target_dir.resolve())

    source_path = str(source_dir.resolve())
    logger.info(
        "Prepared migration upload migration_name=%s user=%s source_path=%s target_path=%s",
        migration_name, uid, source_path, target_path,
    )
    return {
        "migration_name": migration_name,
        "source_path": source_path,
        "target_path": target_path,
        "upload_id": work_id,
    }


async def execute_agent_team(task_id: str, request: RunTeamRequest, owner_user_id: str):
    logger.info("[TASK %s] STARTED | source_path=%r owner=%r", task_id, request.source_path, owner_user_id)
    create_task(task_id, user_id=owner_user_id, status=AgentConstants.TASK_STATUS_RUNNING)
    try:
        # Background task: bind the authenticated user (ignore client-supplied user_id on the body).
        try:
            current_user.set(SimpleNamespace(id=int(str(owner_user_id).strip())))
        except (TypeError, ValueError) as exc:
            logger.warning("Task %s: could not set current_user from owner_user_id=%r: %s", task_id, owner_user_id, exc)

        effective_user_id = str(owner_user_id).strip()
        orchestrator = WorkflowOrchestrator()
        result = await orchestrator.run_workflow(
            request.source_path,
            request.migration_name,
            request.target_language,
            request.description,
            request.target_path,
            request.github_token or "",
            effective_user_id,
            task_id=task_id,
        )
        try:
            workflow_outcome = json.loads(result) if isinstance(result, str) else result
        except (TypeError, ValueError):
            workflow_outcome = {}
        release_ready = isinstance(workflow_outcome, dict) and bool(workflow_outcome.get("release_ready"))
        completed_payload = {
            "kind": "completed" if release_ready else "blocked",
            "output": result,
            "release_ready": release_ready,
            "message": (workflow_outcome.get("message") if isinstance(workflow_outcome, dict) else None),
            "plan": [
                {"name": name, "status": "complete", "percent": int(((i + 1) / 7) * 100)}
                for i, name in enumerate([
                    "Scan source", "Verify scan", "Build knowledge base", "Plan migration",
                    "Verify plan", "Convert code", "Post-migration engineering",
                ])
            ],
        }
        if release_ready:
            update_task(
                task_id,
                status=AgentConstants.TASK_STATUS_COMPLETED,
                result=json.dumps(completed_payload),
                mark_completed=True,
            )
        else:
            update_task(
                task_id,
                status=AgentConstants.TASK_STATUS_FAILED,
                result=json.dumps(completed_payload),
                error=completed_payload["message"] or "Post-migration release gate failed",
                mark_completed=True,
            )
    except Exception as e:
        logger.exception(f"[TASK {task_id}] FAILED")
        update_task(
            task_id,
            status=AgentConstants.TASK_STATUS_FAILED,
            error=str(e),
            mark_completed=True,
        )


@router.get("/migration_list/list")
async def get_user_migrations(user=Depends(get_current_user)):
    try:
        service = MigrationListService()
        migrations = service.get_user_migrations(user.id)
        return {"user": user.id, "migrations": migrations, "count": len(migrations)}
    except Exception as e:
        raise HTTPException(status_code=ServiceConstants.CODE500, detail=str(e))


@router.get("/v1/migration/list")
async def get_user_migrations_v1(user=Depends(get_current_user)):
    return await get_user_migrations(user=user)


@router.get("/v1/migration/status/{migration_name}")
async def get_migration_status_v1(migration_name: str, user=Depends(get_current_user)):
    migration_name = _validate_migration_name(migration_name)
    migration_dir = _migration_dest_dir(str(user.id), migration_name)
    if not migration_dir.exists():
        raise HTTPException(
            status_code=ServiceConstants.CODE404,
            detail=AgentConstants.MIGRATION_NOT_FOUND_FOR_USER.format(
                migration_name=migration_name,
                user_id=user.id,
            ),
        )
    processed_zip = migration_dir / f"{migration_name}_processed.zip"
    status = ServiceConstants.COMPLETE if processed_zip.exists() else ServiceConstants.IN_PROGRESS
    return {
        "user_id": str(user.id),
        "migration_name": migration_name,
        "status": status,
        "path": str(migration_dir),
    }


@router.delete("/v1/migration/temp/{migration_name}")
async def delete_migration_temp_v1(migration_name: str, user=Depends(get_current_user)):
    migration_name = _validate_migration_name(migration_name)
    migration_root = Path(PathConstants.TEMP_DIR) / str(user.id) / migration_name
    # if not migration_root.exists():
    #     raise HTTPException(
    #         status_code=ServiceConstants.CODE404,
    #         detail=f"Migration '{migration_name}' not found for user '{user.id}'",
    #     )
    if migration_root.exists():
        shutil.rmtree(str(migration_root), onerror=_remove_readonly)
        
    deleted_rows = delete_migration_data(migration_name=migration_name, user_id=int(user.id))
    return {
        "status": "success",
        "message": f"Temp migration '{migration_name}' deleted in agent_service",
        "deleted_migration_data_rows": deleted_rows,
    }


@router.get("/v1/migration/download/{migration_name}")
async def download_migration_v1(migration_name: str, user=Depends(get_current_user)):
    migration_name = _validate_migration_name(migration_name)
    migration_dir = _migration_dest_dir(str(user.id), migration_name)
    zip_path = migration_dir / f"{migration_name}_processed.zip"
    if not zip_path.exists() or not zip_path.is_file():
        # Distinguish a genuinely missing artifact from a red quality gate.
        # A red gate is allowed to remain non-release-ready, but the demo
        # artifact should normally still be downloadable when packaging succeeded.
        quality_path = migration_dir / "Migrated Code" / ".migration" / "quality_report.json"
        if not quality_path.exists():
            quality_path = migration_dir / "migrated_code" / ".migration" / "quality_report.json"
        detail = {
            "code": "ARTIFACT_NOT_AVAILABLE",
            "migration_name": migration_name,
            "message": "Converted artifact is not available yet.",
        }
        if quality_path.exists():
            try:
                report = json.loads(quality_path.read_text(encoding="utf-8"))
                detail["status"] = report.get("status")
                detail["release_ready"] = bool(report.get("release_ready"))
                detail["reason"] = report.get("message")
            except Exception:
                pass
        raise HTTPException(status_code=409, detail=detail)
    return FileResponse(
        path=zip_path,
        filename=f"{migration_name}.zip",
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={migration_name}.zip"},
    )


@router.post("/v1/teams/run", response_model=TaskAcceptedResponse)
async def run_agent_team(
    request: RunTeamRequest,
    background_tasks: BackgroundTasks,
    user=Depends(get_current_user),
):
    current_user.set(user)
    task_id = str(uuid.uuid4())
    logger.info("POST /v1/teams/run | task_id=%s", task_id)

    # Stack detection uses an LLM and can take longer than the UI's request
    # timeout.  Do it inside execute_agent_team, where it belongs, after this
    # endpoint has returned a task ID.
    background_tasks.add_task(execute_agent_team, task_id, request, str(user.id))
    return TaskAcceptedResponse(
        task_id=task_id,
        message=AgentConstants.AGENT_TEAM_EXECUTION_QUEUED,
        detected_target_language=(request.target_language or "").strip().lower() or None,
    )


@router.get("/v1/tasks/{task_id}", response_model=TaskStatusResponse)
async def get_task_status(task_id: str, user=Depends(get_current_user)):
    current_user.set(user)
    data = get_task(task_id)
    if data is None:
        raise HTTPException(status_code=404, detail=AgentConstants.TASK_NOT_FOUND)
    if str(data.get("user_id") or "") != str(user.id):
        raise HTTPException(status_code=404, detail=AgentConstants.TASK_NOT_FOUND)
    return TaskStatusResponse(
        status=data["status"],
        result=data.get("result"),
        error=data.get("error"),
        completed_at=data.get("completed_at"),
    )


@router.post("/v1/architecture/plan", response_model=ArchitectureResponse)
async def get_architecture_plan(
    request: ArchitectureRequest,
    user=Depends(get_current_user),
) -> ArchitectureResponse:
    current_user.set(user)
    selected_architecture = AgentConstants.ARCHITECTURE_MAP.get(
        request.architecture_option,
        request.architecture_option,
    )
    message = AgentConstants.ARCHITECTURE_SELECTED_FOR_TARGET_PATH.format(
        selected_architecture=selected_architecture,
        target_path=request.target_path,
    )
    return ArchitectureResponse(selected_architecture=selected_architecture, message=message)


@router.get("/v1/health")
async def health_check():
    return {AgentConstants.TASK_STATUS: AgentConstants.HEALTHY}


@router.post("/v1/chat/ask", response_model=ChatAskResponse)
async def chat_ask(
    request: ChatAskRequest,
    user=Depends(get_current_user),
) -> ChatAskResponse:
    try:
        try:
            current_user.set(user)
        except Exception:
            pass
        _set_migration_context(request.migration_name, user)
        from app.application.agents.chat.chat_tools import ask_kb_impl

        ask_kb_callable = _resolve_tool_callable(ask_kb_impl)
        answer = ask_kb_callable(
            question=request.question,
            source_file_path=request.source_file_path,
            is_target=bool(request.is_target),
        )
        return ChatAskResponse(answer=str(answer))
    except Exception as e:
        logger.exception("Chat ask failed")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/v1/report/migration")
async def migration_report(
    request: MigrationReportRequest,
    user=Depends(get_current_user),
):
    try:
        try:
            current_user.set(user)
        except Exception:
            pass
        _set_migration_context(request.migration_name, user)
        from app.infrastructure.utils.reporting_manager import generate_migration_comparison_report

        report_callable = _resolve_tool_callable(generate_migration_comparison_report)
        report = report_callable(
            request.migration_name,
            persist=bool(request.persist),
            include_markdown=bool(request.include_markdown),
            require_migrated=bool(request.require_migrated),
        )
        return report
    except Exception as e:
        logger.exception("Migration report generation failed")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/v1/showcase/migration")
async def migration_showcase(
    request: MigrationShowcaseRequest,
    user=Depends(get_current_user),
):
    try:
        try:
            current_user.set(user)
        except Exception:
            pass
        _set_migration_context(request.migration_name, user)
        from app.infrastructure.utils.showcase_manager import generate_showcase_bundle

        showcase_callable = _resolve_tool_callable(generate_showcase_bundle)
        bundle = showcase_callable(request.migration_name, persist=bool(request.persist))
        return bundle
    except Exception as e:
        logger.exception("Migration showcase generation failed")
        raise HTTPException(status_code=500, detail=str(e)) from e


def _run_post_migration_background(
    migration_name: str,
    migrated_code_path,
    persist: bool,
    user,
) -> None:
    """Background task: sets context vars and runs the full post-migration workflow."""
    try:
        current_user.set(user)
    except Exception:
        pass
    try:
        _set_migration_context(migration_name, user)
    except Exception:
        pass
    try:
        from app.application.agents.post_migration.post_migration_tools import (
            run_post_migration_analysis_impl,
        )
        runner = _resolve_tool_callable(run_post_migration_analysis_impl)
        runner(
            migration_name=migration_name,
            migrated_code_path=migrated_code_path,
            persist=persist,
        )
    except Exception:
        logger.exception("Post migration background run failed for '%s'", migration_name)


@router.post("/v1/post_migration/run", status_code=202)
async def run_post_migration(
    request: PostMigrationRunRequest,
    background_tasks: BackgroundTasks,
    user=Depends(get_current_user),
):
    try:
        current_user.set(user)
    except Exception:
        pass
    background_tasks.add_task(
        _run_post_migration_background,
        request.migration_name,
        request.migrated_code_path,
        bool(request.persist),
        user,
    )
    return {
        "status": "accepted",
        "migration_name": request.migration_name,
        "message": "Post-migration analysis started. Progress updates will be sent via workflow event stream.",
    }


@router.post("/v1/post_migration/quality")
async def post_migration_quality(
    request: PostMigrationQualityRequest,
    user=Depends(get_current_user),
):
    try:
        try:
            current_user.set(user)
        except Exception:
            pass
        _set_migration_context(request.migration_name, user)
        from app.application.agents.post_migration.post_migration_tools import (
            run_migrated_code_quality_check_impl,
        )

        runner = _resolve_tool_callable(run_migrated_code_quality_check_impl)
        raw_result = runner(
            migration_name=request.migration_name,
            migrated_code_path=request.migrated_code_path,
        )
        if isinstance(raw_result, dict):
            return raw_result
        if not isinstance(raw_result, str):
            return {"status": "error", "message": str(raw_result)}
        try:
            return json.loads(raw_result)
        except Exception:
            return {
                AgentConstants.TASK_STATUS: AgentConstants.TASK_STATUS_ERROR,
                AgentConstants.RESPONSE_MESSAGE: str(raw_result),
            }
    except Exception as e:
        logger.exception("Post migration quality check failed")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/v1/migration/semantic-verification/{migration_name}")
async def get_semantic_verification(migration_name: str, user=Depends(get_current_user)):
    """Return evidence-based source/target contract and behavioral verification."""
    migration_name = _validate_migration_name(migration_name)
    from app.infrastructure.utils.semantic_verifier import verify_migration_semantics
    from app.infrastructure.utils.migration_context_resolver import resolve_source_path

    # HTTP requests do not inherit the orchestrator ContextVars. Resolve the
    # user's canonical migration directory directly from the authenticated user.
    root = _migration_dest_dir(str(user.id), migration_name)
    candidates = [root / "Migrated Code", root / "migrated_code"]
    migrated = next((p for p in candidates if p.exists() and p.is_dir()), None)
    if migrated is None:
        raise HTTPException(status_code=404, detail="Migrated project not found")
    artifact = migrated / ".migration" / "semantic_verification.json"
    if artifact.exists():
        try:
            data = json.loads(artifact.read_text(encoding="utf-8"))
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Could not read semantic verification: {exc}") from exc
    else:
        source = resolve_source_path()
        data = verify_migration_semantics(source or None, migrated, migration_name=migration_name, persist=True)
    return {"migration_name": migration_name, "data": data}


@router.get("/v1/migration/evidence/{migration_name}")
async def get_migration_evidence(migration_name: str, user=Depends(get_current_user)):
    """Return persisted security, provenance and source-to-target traceability evidence."""
    migration_name = _validate_migration_name(migration_name)
    # HTTP requests do not inherit the orchestrator ContextVars. Resolve the
    # user's canonical migration directory directly from the authenticated user.
    root = _migration_dest_dir(str(user.id), migration_name)
    candidates = [root / "Migrated Code", root / "migrated_code"]
    migrated = next((p for p in candidates if p.exists() and p.is_dir()), None)
    if migrated is None:
        raise HTTPException(status_code=404, detail="Migrated project not found")
    out = migrated / ".migration"
    data = {}
    for name in ("security_review", "provenance_manifest", "traceability_matrix"):
        path = out / f"{name}.json"
        if path.exists():
            try:
                data[name] = json.loads(path.read_text(encoding="utf-8"))
            except Exception as exc:
                data[name] = {"status":"error","message":str(exc)}
    return {"migration_name": migration_name, "data": data}


@router.get("/v1/migration/analysis/{migration_name}")
async def get_migrated_analysis(migration_name: str, user=Depends(get_current_user)):
    """Return the deterministic post-migration architecture intelligence bundle."""
    migration_name = _validate_migration_name(migration_name)
    # HTTP requests do not inherit the orchestrator ContextVars. Resolve the
    # user's canonical migration directory directly from the authenticated user.
    root = _migration_dest_dir(str(user.id), migration_name)
    candidates = [root / "Migrated Code", root / "migrated_code"]
    migrated = next((p for p in candidates if p.exists() and p.is_dir()), None)
    if migrated is None:
        raise HTTPException(status_code=404, detail="Migrated project not found")
    artifact = migrated / ".migration" / "architecture_analysis.json"
    if not artifact.exists():
        from app.infrastructure.utils.migrated_architecture_analyzer import analyze_migrated_architecture
        data = analyze_migrated_architecture(migrated, migration_name=migration_name, persist=True)
    else:
        try:
            data = json.loads(artifact.read_text(encoding="utf-8"))
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Could not read architecture analysis: {exc}") from exc
    return {"migration_name": migration_name, "data": data}


@router.get("/v1/artifact/{migration_name}")
async def get_artifact(
    migration_name: str,
    artifact_type: str,
    scope: int = 1,
    user=Depends(get_current_user),
):
    """Generic endpoint to fetch any JSON artifact from DB by artifact_type.
    Supported types: knowledge_graph, migration_plan, ast, tech, dependency_graph, etc.
    """
    from app.infrastructure.repositories.json_artifact_repository import fetch_json_artifact

    try:
        data = fetch_json_artifact(
            migration_name=migration_name,
            artifact_type=artifact_type,
            user_id=int(user.id),
            scope=scope,
        )
    except Exception as exc:
        logger.exception("Failed to fetch artifact '%s' for migration '%s'", artifact_type, migration_name)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    if data is None:
        raise HTTPException(
            status_code=404,
            detail=f"Artifact '{artifact_type}' not found for migration '{migration_name}'",
        )
    return {"migration_name": migration_name, "artifact_type": artifact_type, "data": data}


@router.get("/")
async def root():
    return {AgentEventMessages.Message: ServiceConstants.AGENT_RUNNING_MESSAGE}
