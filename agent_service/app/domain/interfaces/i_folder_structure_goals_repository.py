from abc import ABC, abstractmethod
from typing import Any, Optional


class IFolderStructureGoalsRepository(ABC):
    """Abstract interface for folder_structure_with_goals persistence (DB)."""

    @abstractmethod
    def set_folder_structure_goals(
        self,
        migration_name: str,
        payload: Any,
        user_id: Optional[int] = None,
        scope: int = 1,
        save_artifact: bool = True,
    ) -> Optional[int]:
        """Save full folder_structure_with_goals tree into normalized tables."""
        pass

    @abstractmethod
    def fetch_folder_structure_goals(
        self,
        migration_name: str,
        user_id: Optional[int] = None,
        scope: int = 1,
    ) -> Optional[Any]:
        """Fetch folder_structure_with_goals tree from normalized store (fallback artifact)."""
        pass
