from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List


class IMigrationDataRepository(ABC):
    """Interface for direct access to migration_data table."""

    @abstractmethod
    def upsert_migration_data(
        self,
        migration_name: str,
        user_id: Optional[int] = None,
        created_by: Optional[int] = None,
        updated_by: Optional[int] = None,
    ) -> Optional[int]:
        """Insert or update a migration_data row and return row id."""
        pass

    @abstractmethod
    def fetch_migration_data(
        self,
        migration_name: str,
        user_id: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:
        """Fetch one migration_data row by migration_name and optional user_id."""
        pass

    @abstractmethod
    def list_migration_names_for_user(self, user_id: int) -> List[str]:
        """Return migration_name values for the user, newest first, excluding null names."""
        pass

    @abstractmethod
    def delete_migration_data(
        self,
        migration_name: str,
        user_id: int,
    ) -> int:
        """Delete migration_data rows matching user_id and migration_name. Returns deleted count."""
        pass

