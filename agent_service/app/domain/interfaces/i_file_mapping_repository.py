from abc import ABC, abstractmethod
from typing import Any, Optional


class IFileMappingRepository(ABC):
    """Abstract interface for file_mapping.json persistence (DB)."""

    @abstractmethod
    def set_file_mapping(
        self,
        migration_name: str,
        payload: Any,
        user_id: Optional[int] = None,
        scope: int = 1,
        save_artifact: bool = True,
    ) -> Optional[int]:
        """Save full file_mapping list into normalized table."""
        pass

    @abstractmethod
    def fetch_file_mapping(
        self,
        migration_name: str,
        user_id: Optional[int] = None,
        scope: int = 1,
    ) -> Optional[Any]:
        """Fetch file_mapping list from normalized store (fallback artifact)."""
        pass
