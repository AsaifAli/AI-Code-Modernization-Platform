"""
Repository for normalized file_mapping.json storage.
Implements IFileMappingRepository; use get_file_mapping_repository() for interface.
"""
import json
import logging
from typing import Any, Optional

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.domain.interfaces.i_file_mapping_repository import IFileMappingRepository
from app.infrastructure.db.db_connection import engine
from app.infrastructure.utils.Constants.app_constants import MigrationScope

logger = logging.getLogger(__name__)

# Re-export for callers (same semantics as migration_scan_result scope)
SCOPE_SOURCE = MigrationScope.SCOPE_SOURCE
SCOPE_TARGET = MigrationScope.SCOPE_TARGET
SCOPE_SOURCE_NAME = MigrationScope.SCOPE_SOURCE_NAME
SCOPE_TARGET_NAME = MigrationScope.SCOPE_TARGET_NAME


class FileMappingRepository(IFileMappingRepository):
    """Concrete implementation of IFileMappingRepository using stored procedures."""

    def set_file_mapping(
        self,
        migration_name: str,
        payload: Any,
        user_id: Optional[int] = None,
        scope: int = SCOPE_SOURCE,
        save_artifact: bool = True,
    ) -> Optional[int]:
        if engine is None:
            logger.warning("Database not configured. Skipping file_mapping save.")
            return None
        try:
            payload_str = json.dumps(payload)
            with Session(engine) as session:
                stmt = select(
                    func.set_file_mapping(
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
            logger.error("Failed to save file_mapping: %s", exc)
            return None

    def fetch_file_mapping(
        self,
        migration_name: str,
        user_id: Optional[int] = None,
        scope: int = SCOPE_SOURCE,
    ) -> Optional[Any]:
        if engine is None:
            logger.warning("Database not configured. Skipping file_mapping fetch.")
            return None
        try:
            with Session(engine) as session:
                stmt = select(
                    func.get_file_mapping(
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
            logger.error("Failed to fetch file_mapping: %s", exc)
            return None


_default_repository: Optional[IFileMappingRepository] = None


def get_file_mapping_repository() -> IFileMappingRepository:
    """Return the default IFileMappingRepository implementation."""
    global _default_repository
    if _default_repository is None:
        _default_repository = FileMappingRepository()
    return _default_repository


def set_file_mapping(
    migration_name: str,
    payload: Any,
    user_id: Optional[int] = None,
    scope: int = SCOPE_SOURCE,
    save_artifact: bool = True,
) -> Optional[int]:
    """Module-level helper wrapper for set_file_mapping."""
    return get_file_mapping_repository().set_file_mapping(
        migration_name=migration_name,
        payload=payload,
        user_id=user_id,
        scope=scope,
        save_artifact=save_artifact,
    )


def fetch_file_mapping(
    migration_name: str,
    user_id: Optional[int] = None,
    scope: int = SCOPE_SOURCE,
) -> Optional[Any]:
    """Module-level helper wrapper for fetch_file_mapping."""
    return get_file_mapping_repository().fetch_file_mapping(
        migration_name=migration_name,
        user_id=user_id,
        scope=scope,
    )
