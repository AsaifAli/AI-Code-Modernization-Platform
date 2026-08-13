"""
Repository for normalized folder_structure_with_goals storage.
Implements IFolderStructureGoalsRepository; use get_folder_structure_goals_repository() for interface.
"""
import json
import logging
from typing import Any, Optional

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.domain.interfaces.i_folder_structure_goals_repository import (
    IFolderStructureGoalsRepository,
)
from app.infrastructure.db.db_connection import engine
from app.infrastructure.utils.Constants.app_constants import MigrationScope

logger = logging.getLogger(__name__)

# Re-export for callers (same semantics as migration_scan_result scope)
SCOPE_SOURCE = MigrationScope.SCOPE_SOURCE
SCOPE_TARGET = MigrationScope.SCOPE_TARGET
SCOPE_SOURCE_NAME = MigrationScope.SCOPE_SOURCE_NAME
SCOPE_TARGET_NAME = MigrationScope.SCOPE_TARGET_NAME


class FolderStructureGoalsRepository(IFolderStructureGoalsRepository):
    """Concrete implementation of IFolderStructureGoalsRepository using stored procedures."""

    def set_folder_structure_goals(
        self,
        migration_name: str,
        payload: Any,
        user_id: Optional[int] = None,
        scope: int = SCOPE_SOURCE,
        save_artifact: bool = True,
    ) -> Optional[int]:
        if engine is None:
            logger.warning("Database not configured. Skipping folder_structure_with_goals save.")
            return None
        try:
            payload_str = json.dumps(payload)
            with Session(engine) as session:
                stmt = select(
                    func.set_folder_structure_goals(
                        migration_name,
                        payload_str,
                        user_id,
                        scope,
                        save_artifact,
                    )
                )
                value = session.execute(stmt).scalar_one_or_none()
                session.commit()
                return int(value) if value is not None else None
        except Exception as exc:
            logger.error("Failed to save folder_structure_with_goals: %s", exc)
            return None

    def fetch_folder_structure_goals(
        self,
        migration_name: str,
        user_id: Optional[int] = None,
        scope: int = SCOPE_SOURCE,
    ) -> Optional[Any]:
        if engine is None:
            logger.warning("Database not configured. Skipping folder_structure_with_goals fetch.")
            return None
        try:
            with Session(engine) as session:
                stmt = select(
                    func.get_folder_structure_goals_tree(
                        migration_name,
                        user_id,
                        scope,
                    )
                )
                value = session.execute(stmt).scalar_one_or_none()
                if value is None:
                    return None
                out = value
                if isinstance(out, (dict, list)):
                    return out
                if isinstance(out, str):
                    return json.loads(out)
                return json.loads(str(out))
        except Exception as exc:
            logger.error("Failed to fetch folder_structure_with_goals: %s", exc)
            return None


_default_repository: Optional[IFolderStructureGoalsRepository] = None


def get_folder_structure_goals_repository() -> IFolderStructureGoalsRepository:
    """Return the default IFolderStructureGoalsRepository implementation."""
    global _default_repository
    if _default_repository is None:
        _default_repository = FolderStructureGoalsRepository()
    return _default_repository


def set_folder_structure_goals(
    migration_name: str,
    payload: Any,
    user_id: Optional[int] = None,
    scope: int = SCOPE_SOURCE,
    save_artifact: bool = True,
) -> Optional[int]:
    """Module-level helper wrapper for set_folder_structure_goals."""
    return get_folder_structure_goals_repository().set_folder_structure_goals(
        migration_name=migration_name,
        payload=payload,
        user_id=user_id,
        scope=scope,
        save_artifact=save_artifact,
    )


def fetch_folder_structure_goals(
    migration_name: str,
    user_id: Optional[int] = None,
    scope: int = SCOPE_SOURCE,
) -> Optional[Any]:
    """Module-level helper wrapper for fetch_folder_structure_goals."""
    return get_folder_structure_goals_repository().fetch_folder_structure_goals(
        migration_name=migration_name,
        user_id=user_id,
        scope=scope,
    )
