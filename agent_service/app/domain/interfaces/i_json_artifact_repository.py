from abc import ABC, abstractmethod
from typing import Any, Optional, Sequence


class IJsonArtifactRepository(ABC):
    """Abstract interface for migration JSON artifact persistence (DB)."""

    @abstractmethod
    def save_json_artifact(
        self,
        migration_name: str,
        artifact_type: str,
        payload: Any,
        user_id: Optional[int] = None,
        scope: int = 1,
        update_key: Optional[str] = None,
    ) -> Optional[int]:
        """Persist artifact via set_migration_artifact (full payload or key-level patch)."""
        pass

    @abstractmethod
    def fetch_json_artifact(
        self,
        migration_name: str,
        artifact_type: str,
        user_id: Optional[int] = None,
        scope: int = 1,
        keys: Optional[Sequence[str]] = None,
    ) -> Optional[Any]:
        """Fetch latest artifact payload (full JSON or selected top-level keys)."""
        pass
