"""
Repository for normalized migration_scan_result storage.
Implements IMigrationScanResultRepository; use get_migration_scan_result_repository() for interface.
"""
import json
import logging
from typing import Optional

from sqlalchemy import text, select, func
from sqlalchemy.orm import Session

from app.domain.interfaces.i_migration_scan_result_repository import (
    IMigrationScanResultRepository,
)
from app.infrastructure.db.db_connection import engine
from app.infrastructure.utils.Constants.app_constants import MigrationScope

logger = logging.getLogger(__name__)


class MigrationScanResultRepository(IMigrationScanResultRepository):
    """Concrete implementation of IMigrationScanResultRepository using stored procedures."""

    def save_migration_scan_result(
        self,
        response: dict,
        migration_name: str,
        migration_id: Optional[int] = None,
        user_id: Optional[int] = None,
        scope: int = MigrationScope.SCOPE_SOURCE,
    ) -> Optional[int]:
        if engine is None:
            logger.warning("Database not configured. Skipping migration_scan_result save.")
            return None
        try:
            payload = json.dumps(response)
            with Session(engine) as session:
                stmt = select(
                    func.set_migration_scan_result(
                        payload,
                        migration_id,
                        migration_name,
                        user_id,
                        scope,
                    )
                )
                value = session.execute(stmt).scalar_one_or_none()
                session.commit()
                return int(value) if value is not None else None
        except Exception as exc:
            logger.error("Failed to save migration_scan_result: %s", exc)
            return None

    def migration_scan_result_exists(
        self,
        migration_name: str,
        user_id: Optional[int] = None,
        scope: int = MigrationScope.SCOPE_SOURCE,
    ) -> bool:
        if engine is None:
            return False
        try:
            with engine.connect() as conn:
                r = conn.execute(
                    text(
                        """
                        SELECT 1 FROM migration_scan_result
                        WHERE migration_name = :p_migration_name
                          AND ( :p_user_id IS NULL OR user_id = :p_user_id )
                          AND scope = :p_scope
                        LIMIT 1
                        """
                    ),
                    {
                        "p_migration_name": migration_name,
                        "p_user_id": user_id,
                        "p_scope": scope,
                    },
                )
                row = r.fetchone()
                return row is not None
        except Exception as exc:
            logger.warning("Failed to check migration_scan_result exists: %s", exc)
            return False

    def get_migration_scan_result(
        self,
        migration_name: str,
        user_id: Optional[int] = None,
        scope: int = MigrationScope.SCOPE_SOURCE,
    ) -> Optional[dict]:
        if engine is None:
            logger.warning("Database not configured. Skipping migration_scan_result fetch.")
            return None
        try:
            with Session(engine) as session:
                stmt = select(
                    func.get_migration_scan_result(
                        migration_name,
                        user_id,
                        scope,
                    )
                )
                value = session.execute(stmt).scalar_one_or_none()
                if value is None:
                    return None
                out = value
                if isinstance(out, dict):
                    return out
                if isinstance(out, str):
                    return json.loads(out)
                return json.loads(str(out))
        except Exception as exc:
            logger.error("Failed to fetch migration_scan_result: %s", exc)
            return None


_default_repository: Optional[IMigrationScanResultRepository] = None


def get_migration_scan_result_repository() -> IMigrationScanResultRepository:
    """Return the default IMigrationScanResultRepository implementation."""
    global _default_repository
    if _default_repository is None:
        _default_repository = MigrationScanResultRepository()
    return _default_repository
