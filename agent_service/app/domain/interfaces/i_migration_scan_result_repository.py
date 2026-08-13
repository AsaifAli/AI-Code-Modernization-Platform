from abc import ABC, abstractmethod
from typing import Any, Optional


class IMigrationScanResultRepository(ABC):
    """Abstract interface for migration scan result persistence (DB)."""

    @abstractmethod
    def save_migration_scan_result(
        self,
        response: dict,
        migration_name: str,
        migration_id: Optional[int] = None,
        user_id: Optional[int] = None,
        scope: int = 1,
    ) -> Optional[int]:
        """Save response into normalized tables. Returns migration_scan_result.id or None."""
        pass

    @abstractmethod
    def migration_scan_result_exists(
        self,
        migration_name: str,
        user_id: Optional[int] = None,
        scope: int = 1,
    ) -> bool:
        """Return True if a row exists for the given migration_name, user_id, scope."""
        pass

    @abstractmethod
    def get_migration_scan_result(
        self,
        migration_name: str,
        user_id: Optional[int] = None,
        scope: int = 1,
    ) -> Optional[dict]:
        """Load scan result as response.json-shaped dict. Returns None if not found."""
        pass
