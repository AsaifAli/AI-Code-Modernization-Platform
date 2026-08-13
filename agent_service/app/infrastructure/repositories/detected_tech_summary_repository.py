"""
Repository for normalized detected_tech_summarized.txt storage.
Implements IDetectedTechSummaryRepository; use get_detected_tech_summary_repository() for interface.
"""
import logging
import os
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.domain.interfaces.i_detected_tech_summary_repository import (
    IDetectedTechSummaryRepository,
)
from app.infrastructure.db.db_connection import engine
from app.infrastructure.repositories.json_artifact_repository import (
    fetch_json_artifact as fetch_json_artifact_record,
    save_json_artifact as save_json_artifact_record,
)
from app.infrastructure.utils.Constants.app_constants import MigrationScope

logger = logging.getLogger(__name__)
DB_FUNCTION_SCHEMA = os.getenv("DB_FUNCTION_SCHEMA", "public").strip() or "public"
DETECTED_TECH_ARTIFACT_TYPE = "detected_tech_summarized"

# Re-export for callers
SCOPE_SOURCE = MigrationScope.SCOPE_SOURCE
SCOPE_TARGET = MigrationScope.SCOPE_TARGET
SCOPE_SOURCE_NAME = MigrationScope.SCOPE_SOURCE_NAME
SCOPE_TARGET_NAME = MigrationScope.SCOPE_TARGET_NAME


class DetectedTechSummaryRepository(IDetectedTechSummaryRepository):
    """Detected tech summary persistence with JSON-artifact primary path."""

    @staticmethod
    def _set_detected_tech_summary_func():
        return getattr(getattr(func, DB_FUNCTION_SCHEMA), "set_detected_tech_summary")

    @staticmethod
    def _get_detected_tech_summary_func():
        return getattr(getattr(func, DB_FUNCTION_SCHEMA), "get_detected_tech_summary")

    def set_detected_tech_summary(
        self,
        migration_name: str,
        content: str,
        user_id: Optional[int] = None,
        scope: int = SCOPE_SOURCE,
        save_artifact: bool = True,
    ) -> Optional[int]:
        # IMPORTANT:
        # Avoid calling set_detected_tech_summary SP because some DB deployments
        # have ambiguous set_migration_artifact overloads inside that function body.
        # Persist via generic JSON artifact path (same data, safer call surface).
        if not save_artifact:
            return 0
        try:
            return save_json_artifact_record(
                migration_name=migration_name,
                artifact_type=DETECTED_TECH_ARTIFACT_TYPE,
                payload={"content": content},
                user_id=user_id,
                scope=scope,
                update_key="content",
            )
        except Exception as exc:
            logger.error(
                "Failed to save detected tech summary (artifact path, schema=%s): %s",
                DB_FUNCTION_SCHEMA,
                exc,
            )
            return None

    def fetch_detected_tech_summary(
        self,
        migration_name: str,
        user_id: Optional[int] = None,
        scope: int = SCOPE_SOURCE,
    ) -> Optional[str]:
        # Primary read path: JSON artifact store.
        try:
            value = fetch_json_artifact_record(
                migration_name=migration_name,
                artifact_type=DETECTED_TECH_ARTIFACT_TYPE,
                user_id=user_id,
                scope=scope,
            )
            if isinstance(value, dict):
                content = value.get("content")
                return str(content) if content is not None else None
            if isinstance(value, str):
                return value
        except Exception as exc:
            logger.warning("Artifact fetch for detected tech summary failed: %s", exc)

        # Legacy fallback: old stored procedure (for existing DB data only).
        if engine is None:
            logger.warning("Database not configured. Skipping detected tech summary fetch.")
            return None
        try:
            with Session(engine) as session:
                stmt = select(
                    self._get_detected_tech_summary_func()(
                        migration_name,
                        user_id,
                        scope,
                    )
                )
                value = session.execute(stmt).scalar_one_or_none()
                return str(value) if value is not None else None
        except Exception as exc:
            try:
                with Session(engine) as session:
                    stmt = select(
                        func.get_detected_tech_summary(
                            migration_name,
                            user_id,
                            scope,
                        )
                    )
                    value = session.execute(stmt).scalar_one_or_none()
                    return str(value) if value is not None else None
            except Exception:
                logger.error(
                    "Failed to fetch detected tech summary (schema=%s): %s",
                    DB_FUNCTION_SCHEMA,
                    exc,
                )
                return None


_default_repository: Optional[IDetectedTechSummaryRepository] = None


def get_detected_tech_summary_repository() -> IDetectedTechSummaryRepository:
    """Return the default IDetectedTechSummaryRepository implementation."""
    global _default_repository
    if _default_repository is None:
        _default_repository = DetectedTechSummaryRepository()
    return _default_repository


def set_detected_tech_summary(
    migration_name: str,
    content: str,
    user_id: Optional[int] = None,
    scope: int = SCOPE_SOURCE,
    save_artifact: bool = True,
) -> Optional[int]:
    """Module-level helper wrapper for set_detected_tech_summary."""
    return get_detected_tech_summary_repository().set_detected_tech_summary(
        migration_name=migration_name,
        content=content,
        user_id=user_id,
        scope=scope,
        save_artifact=save_artifact,
    )


def fetch_detected_tech_summary(
    migration_name: str,
    user_id: Optional[int] = None,
    scope: int = SCOPE_SOURCE,
) -> Optional[str]:
    """Module-level helper wrapper for fetch_detected_tech_summary."""
    return get_detected_tech_summary_repository().fetch_detected_tech_summary(
        migration_name=migration_name,
        user_id=user_id,
        scope=scope,
    )
