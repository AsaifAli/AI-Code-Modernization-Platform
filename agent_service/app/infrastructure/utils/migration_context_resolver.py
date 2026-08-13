import logging
from app.infrastructure.utils.Constants.app_constants import AgentConstants
from app.infrastructure.utils.migration_context import (
    migration_name_ctx,
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

logger = logging.getLogger(__name__)

def _resolve(ctx_var, key: str, session_state: dict | None, default=None):
    """
    Read from context var first; fall back to workflow session_state.
    This handles cases where contextvars are lost in parallel threads.
    """
    value = ctx_var.get(None)
    if value:
        return value
    if session_state:
        value = session_state.get(key)
        if value:
            logger.debug(f"[context_resolver] '{key}' resolved from workflow_session_state (contextvars were empty)")
            # Re-hydrate the context var so downstream calls within this thread also work
            ctx_var.set(value)
            return value
    return default


def resolve_migration_name(session_state: dict | None = None) -> str:
    return _resolve(migration_name_ctx, "migration_name", session_state, "")

def resolve_source_path(session_state: dict | None = None) -> str:
    return _resolve(source_path_ctx, "source_path", session_state, "")

def resolve_target_path(session_state: dict | None = None):
    return _resolve(target_path_ctx, "target_path", session_state, None)

def resolve_target_language(session_state: dict | None = None) -> str:
    return _resolve(target_language_ctx, "target_language", session_state, "unknown")


def resolve_description(session_state: dict | None = None) -> str:
    return _resolve(description_ctx, "description", session_state, "")


def resolve_target_framework(session_state: dict | None = None) -> str:
    return _resolve(
        target_framework_ctx,
        "target_framework",
        session_state,
        AgentConstants.DEFAULT_TARGET_FRAMEWORK,
    )


def resolve_target_architecture(session_state: dict | None = None) -> str:
    return _resolve(
        target_architecture_ctx,
        "target_architecture",
        session_state,
        AgentConstants.DEFAULT_TARGET_ARCHITECTURE,
    )


def resolve_is_frontend(session_state: dict | None = None) -> bool:
    return bool(_resolve(is_frontend_ctx, "is_frontend", session_state, False))


def resolve_target_frontend(session_state: dict | None = None) -> str:
    return _resolve(target_frontend_ctx, "target_frontend", session_state, "")


def resolve_target_frontend_architecture(session_state: dict | None = None) -> str:
    return _resolve(
        target_frontend_architecture_ctx,
        "target_frontend_architecture",
        session_state,
        "",
    )
