from abc import ABC, abstractmethod
from typing import Optional


class IDetectedTechSummaryRepository(ABC):
    """Abstract interface for detected_tech_summarized.txt persistence (DB)."""

    @abstractmethod
    def set_detected_tech_summary(
        self,
        migration_name: str,
        content: str,
        user_id: Optional[int] = None,
        scope: int = 1,
        save_artifact: bool = True,
    ) -> Optional[int]:
        """Save detected tech summary text into normalized table."""
        pass

    @abstractmethod
    def fetch_detected_tech_summary(
        self,
        migration_name: str,
        user_id: Optional[int] = None,
        scope: int = 1,
    ) -> Optional[str]:
        """Fetch detected tech summary text from normalized store (fallback artifact)."""
        pass
