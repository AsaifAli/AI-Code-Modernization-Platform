from abc import ABC, abstractmethod
from typing import Any, Dict


class IFileRepository(ABC):
    """Abstract interface for filesystem persistence."""

    @abstractmethod
    def read_json(self, path: str) -> Dict[str, Any]:
        pass

    @abstractmethod
    def write_json(self, path: str, data: Dict[str, Any]) -> None:
        pass

    @abstractmethod
    def write_text(self, path: str, content: str) -> None:
        pass

    @abstractmethod
    def create_directory(self, path: str) -> None:
        pass
