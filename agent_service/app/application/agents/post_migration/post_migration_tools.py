import json
from typing import Optional

from agno.tools import tool

from app.infrastructure.utils.user_context import current_user
from app.infrastructure.utils.event_helper import MigrationEventHelper
from app.infrastructure.utils.enums.migration_event import MigrationEvent
from app.infrastructure.utils.Constants.agent_event import AgentEventMessages
from app.infrastructure.utils.Agent_helpers.post_migration_helper import (
    run_post_migration_pipeline,
    run_migrated_code_quality_check,
)

_post_migration_event_helper = MigrationEventHelper(
    agent_name="conversion",
    event_name="conversion_started",
)


def run_post_migration_analysis_impl(
    migration_name: str,
    migrated_code_path: Optional[str] = None,
    persist: bool = True,
) -> str:
    user = None
    try:
        user = current_user.get()
    except Exception:
        user = None
    result = run_post_migration_pipeline(
        migration_name=migration_name,
        migrated_code_path=migrated_code_path,
        persist=bool(persist),
        user_id=str(getattr(user, "id", "")) if user else None,
    )
    return json.dumps(result, ensure_ascii=False)


@tool
def run_post_migration_analysis(
    migration_name: str,
    migrated_code_path: Optional[str] = None,
    persist: bool = True,
) -> str:
    """Run post-migration analysis for migrated codebase."""
    return run_post_migration_analysis_impl(
        migration_name=migration_name,
        migrated_code_path=migrated_code_path,
        persist=persist,
    )


def run_migrated_code_quality_check_impl(
    migration_name: str,
    migrated_code_path: Optional[str] = None,
) -> str:
    result = run_migrated_code_quality_check(
        migration_name=migration_name,
        migrated_code_path=migrated_code_path,
    )
    return json.dumps(result, ensure_ascii=False)


@tool
def check_migrated_code_quality(
    migration_name: str,
    migrated_code_path: Optional[str] = None,
) -> str:
    """Run quality checks on migrated_code and return a scorecard."""
    return run_migrated_code_quality_check_impl(
        migration_name=migration_name,
        migrated_code_path=migrated_code_path,
    )

