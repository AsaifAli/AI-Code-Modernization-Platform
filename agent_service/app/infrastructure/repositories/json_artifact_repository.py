"""
Repository for migration JSON artifacts (scanner_output, etc.).
Implements IJsonArtifactRepository; use get_json_artifact_repository() for interface.
"""
import logging
from typing import Any, Optional, Sequence
from sqlalchemy.orm import Session
from app.domain.interfaces.i_json_artifact_repository import IJsonArtifactRepository
from app.infrastructure.db.db_connection import engine
from app.infrastructure.utils.Constants.app_constants import MigrationScope
from app.infrastructure.db.models import MigrationArtifact

logger = logging.getLogger(__name__)

# Re-export for callers (same semantics as migration_scan_result scope)
SCOPE_SOURCE = MigrationScope.SCOPE_SOURCE
SCOPE_TARGET = MigrationScope.SCOPE_TARGET
SCOPE_SOURCE_NAME = MigrationScope.SCOPE_SOURCE_NAME
SCOPE_TARGET_NAME = MigrationScope.SCOPE_TARGET_NAME


class JsonArtifactRepository(IJsonArtifactRepository):
    """Concrete implementation of IJsonArtifactRepository using ORM storage.

    The application creates ``migration_artifacts`` through ``init_db()``.  It
    does not install the legacy PostgreSQL helper functions, so querying those
    functions first produced a database error for every artifact access before
    the repository could use its ORM fallback.
    """

    def save_json_artifact(
        self,
        migration_name: str,
        artifact_type: str,
        payload: Any,
        user_id: Optional[int] = None,
        scope: int = SCOPE_SOURCE,
        update_key: Optional[str] = None,
    ) -> Optional[int]:
        if engine is None:
            logger.warning("Database not configured. Skipping migration_artifact save.")
            return None
        try:
            scope_name = MigrationScope.SCOPE_TARGET_NAME if scope == MigrationScope.SCOPE_TARGET else MigrationScope.SCOPE_SOURCE_NAME
            with Session(engine) as session:
                row = session.query(MigrationArtifact).filter(
                    MigrationArtifact.migration_name == migration_name,
                    MigrationArtifact.type == artifact_type,
                    MigrationArtifact.user_id == user_id,
                    MigrationArtifact.scope == scope_name,
                ).order_by(MigrationArtifact.id.desc()).first()
                if row is None:
                    row = MigrationArtifact(migration_name=migration_name, user_id=user_id, type=artifact_type, scope=scope_name, payload=payload)
                    session.add(row)
                elif update_key and isinstance(row.payload, dict) and isinstance(payload, dict):
                    merged_payload = dict(row.payload)
                    merged_payload[update_key.strip()] = payload.get(update_key.strip())
                    row.payload = merged_payload
                else:
                    row.payload = payload
                session.commit()
                session.refresh(row)
                return int(row.id)
        except Exception as exc:
            logger.error("ORM migration_artifact save failed: %s", exc)
            return None

    def fetch_json_artifact(
        self,
        migration_name: str,
        artifact_type: str,
        user_id: Optional[int] = None,
        scope: int = SCOPE_SOURCE,
        keys: Optional[Sequence[str]] = None,
    ) -> Optional[Any]:
        if engine is None:
            logger.warning("Database not configured. Skipping migration_artifact fetch.")
            return None
        try:
            scope_name = MigrationScope.SCOPE_TARGET_NAME if scope == MigrationScope.SCOPE_TARGET else MigrationScope.SCOPE_SOURCE_NAME
            with Session(engine) as session:
                row = session.query(MigrationArtifact).filter(
                    MigrationArtifact.migration_name == migration_name,
                    MigrationArtifact.type == artifact_type,
                    MigrationArtifact.user_id == user_id,
                    MigrationArtifact.scope == scope_name,
                ).order_by(MigrationArtifact.id.desc()).first()
                if row is None:
                    return None
                payload = row.payload
                if keys and isinstance(payload, dict):
                    return {key: payload[key] for key in keys if key in payload}
                return payload
        except Exception as exc:
            logger.error("ORM migration_artifact fetch failed: %s", exc)
            return None


_default_repository: Optional[IJsonArtifactRepository] = None


def get_json_artifact_repository() -> IJsonArtifactRepository:
    """Return the default IJsonArtifactRepository implementation."""
    global _default_repository
    if _default_repository is None:
        _default_repository = JsonArtifactRepository()
    return _default_repository


def save_json_artifact(
    migration_name: str,
    artifact_type: str,
    payload: Any,
    user_id: Optional[int] = None,
    scope: int = SCOPE_SOURCE,
    update_key: Optional[str] = None,
) -> Optional[int]:
    """Module-level convenience wrapper for JsonArtifactRepository.save_json_artifact."""
    return get_json_artifact_repository().save_json_artifact(
        migration_name=migration_name,
        artifact_type=artifact_type,
        payload=payload,
        user_id=user_id,
        scope=scope,
        update_key=update_key,
    )


def fetch_json_artifact(
    migration_name: str,
    artifact_type: str,
    user_id: Optional[int] = None,
    scope: int = SCOPE_SOURCE,
    keys: Optional[Sequence[str]] = None,
) -> Optional[Any]:
    """Module-level convenience wrapper for JsonArtifactRepository.fetch_json_artifact."""
    return get_json_artifact_repository().fetch_json_artifact(
        migration_name=migration_name,
        artifact_type=artifact_type,
        user_id=user_id,
        scope=scope,
        keys=keys,
    )
