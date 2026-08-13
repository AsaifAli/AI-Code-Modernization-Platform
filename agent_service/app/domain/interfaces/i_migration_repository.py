from abc import ABC, abstractmethod
from app.domain.models.legacy_code_entity import LegacyCodeEntity


class IMigrationRepository(ABC):
    """Responsible for storing and retrieving migration-related artifacts."""

    @abstractmethod
    def save_ast(self, migration_name: str, ast_data: dict) -> str:
        pass

    @abstractmethod
    def save_tech_info(self, migration_name: str, tech_data: dict) -> str:
        pass

    @abstractmethod
    def load_legacy_entity(self, migration_name: str) -> LegacyCodeEntity:
        pass
