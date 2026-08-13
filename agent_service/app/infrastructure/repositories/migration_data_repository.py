"""
Repository for direct migration_data table access.
Bypasses stored procedures when DB function signatures drift.
"""
import logging
from typing import Optional, Dict, Any, List

from sqlalchemy import MetaData, Table, select, func, delete
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.domain.interfaces.i_migration_data_repository import IMigrationDataRepository
from app.infrastructure.db.db_connection import engine

logger = logging.getLogger(__name__)


class MigrationDataRepository(IMigrationDataRepository):
    """Concrete implementation for migration_data CRUD using SQLAlchemy."""

    _table: Optional[Table] = None

    @classmethod
    def _migration_data_table(cls) -> Optional[Table]:
        if engine is None:
            return None
        if cls._table is not None:
            return cls._table
        try:
            metadata = MetaData()
            cls._table = Table(
                "migration_data",
                metadata,
                schema="public",
                autoload_with=engine,
            )
            return cls._table
        except Exception as exc:
            logger.error("Failed to reflect migration_data table: %s", exc)
            return None

    def upsert_migration_data(
        self,
        migration_name: str,
        user_id: Optional[int] = None,
        created_by: Optional[int] = None,
        updated_by: Optional[int] = None,
    ) -> Optional[int]:
        table = self._migration_data_table()
        if engine is None or table is None:
            logger.warning("Database not configured. Skipping migration_data upsert.")
            return None

        try:
            with Session(engine) as session:
                insert_values = {
                    "user_id": user_id,
                    "migration_name": migration_name,
                    "created_by": created_by if created_by is not None else user_id,
                    "updated_by": updated_by if updated_by is not None else user_id,
                }
                if "updated_at" in table.c:
                    insert_values["updated_at"] = func.now()

                set_values = {"updated_by": insert_values["updated_by"]}
                if "updated_at" in table.c:
                    set_values["updated_at"] = func.now()

                stmt = (
                    pg_insert(table)
                    .values(**insert_values)
                    .on_conflict_do_update(
                        index_elements=[table.c.user_id, table.c.migration_name],
                        set_=set_values,
                    )
                    .returning(table.c.id)
                )
                value = session.execute(stmt).scalar_one_or_none()
                session.commit()
                return int(value) if value is not None else None
        except Exception as exc:
            logger.error("Failed to upsert migration_data: %s", exc)
            return None

    def fetch_migration_data(
        self,
        migration_name: str,
        user_id: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:
        table = self._migration_data_table()
        if engine is None or table is None:
            logger.warning("Database not configured. Skipping migration_data fetch.")
            return None

        try:
            with Session(engine) as session:
                if user_id is None:
                    stmt = (
                        select(table)
                        .where(table.c.migration_name == migration_name)
                        .order_by(table.c.id.desc())
                        .limit(1)
                    )
                    row = session.execute(stmt).mappings().first()
                else:
                    stmt = (
                        select(table)
                        .where(table.c.migration_name == migration_name)
                        .where(table.c.user_id == user_id)
                        .limit(1)
                    )
                    row = session.execute(stmt).mappings().first()

                return dict(row) if row else None
        except Exception as exc:
            logger.error("Failed to fetch migration_data: %s", exc)
            return None

    def list_migration_names_for_user(self, user_id: int) -> List[str]:
        """List migration_name for user_id from migration_data (authoritative, not Temp)."""
        table = self._migration_data_table()
        if engine is None or table is None:
            logger.warning("Database not configured. Cannot list migration_data.")
            return []
        cnames = {c.name for c in table.c}
        if "migration_name" not in cnames or "user_id" not in cnames:
            return []
        try:
            with Session(engine) as session:
                stmt = select(table.c.migration_name).where(table.c.user_id == int(user_id))
                if "updated_at" in cnames:
                    order_by = [table.c.updated_at.desc().nulls_last()]
                    if "id" in cnames:
                        order_by.append(table.c.id.desc())
                    stmt = stmt.order_by(*order_by)
                elif "id" in cnames:
                    stmt = stmt.order_by(table.c.id.desc())
                else:
                    stmt = stmt.order_by(table.c.migration_name.asc())
                names = [str(n) for n in session.execute(stmt).scalars().all() if n is not None]
                seen: set[str] = set()
                out: List[str] = []
                for n in names:
                    if not n or n in seen:
                        continue
                    seen.add(n)
                    out.append(n)
                return out
        except Exception as exc:
            logger.error("Failed to list migration_data for user: %s", exc)
            return []


    def delete_migration_data(
        self,
        migration_name: str,
        user_id: int,
    ) -> int:
        table = self._migration_data_table()
        if engine is None or table is None:
            logger.warning("Database not configured. Skipping migration_data delete.")
            return 0
        try:
            with Session(engine) as session:
                stmt = (
                    delete(table)
                    .where(table.c.migration_name == migration_name)
                    .where(table.c.user_id == int(user_id))
                )
                result = session.execute(stmt)
                session.commit()
                return result.rowcount
        except Exception as exc:
            logger.error("Failed to delete migration_data: %s", exc)
            return 0


_default_repository: Optional[IMigrationDataRepository] = None


def get_migration_data_repository() -> IMigrationDataRepository:
    """Return default IMigrationDataRepository implementation."""
    global _default_repository
    if _default_repository is None:
        _default_repository = MigrationDataRepository()
    return _default_repository


def upsert_migration_data(
    migration_name: str,
    user_id: Optional[int] = None,
    created_by: Optional[int] = None,
    updated_by: Optional[int] = None,
) -> Optional[int]:
    """Module-level helper wrapper for upsert_migration_data."""
    return get_migration_data_repository().upsert_migration_data(
        migration_name=migration_name,
        user_id=user_id,
        created_by=created_by,
        updated_by=updated_by,
    )


def fetch_migration_data(
    migration_name: str,
    user_id: Optional[int] = None,
) -> Optional[Dict[str, Any]]:
    """Module-level helper wrapper for fetch_migration_data."""
    return get_migration_data_repository().fetch_migration_data(
        migration_name=migration_name,
        user_id=user_id,
    )


def list_migration_names_for_user(user_id: int) -> List[str]:
    """Module-level helper: migration names for user from migration_data table."""
    return get_migration_data_repository().list_migration_names_for_user(user_id)


def delete_migration_data(migration_name: str, user_id: int) -> int:
    """Module-level helper: delete migration_data rows for user_id + migration_name."""
    return get_migration_data_repository().delete_migration_data(
        migration_name=migration_name,
        user_id=user_id,
    )

