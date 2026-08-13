from pathlib import Path
from app.domain.models.legacy_code_entity import LegacyCodeEntity
from app.domain.interfaces.i_migration_repository import IMigrationRepository
from app.infrastructure.repositories.file_repository import FileRepository


class MigrationRepository(IMigrationRepository):
    """Handles persistence of migration artifacts like AST, tech info, and entity data."""

    def __init__(self):
        self.file_repo = FileRepository()

    def save_ast(self, migration_name: str, ast_data: dict) -> str:
        path = Path(migration_name) / "ast.json"
        self.file_repo.write_json(path, ast_data)
        return str(path)

    def save_tech_info(self, migration_name: str, tech_data: dict) -> str:
        path = Path(migration_name) / "tech.json"
        self.file_repo.write_json(path, tech_data)
        return str(path)

    def load_legacy_entity(self, migration_name: str) -> LegacyCodeEntity:
        ast_path = Path(migration_name) / "ast.json"
        tech_path = Path(migration_name) / "tech.json"
        ast = self.file_repo.read_json(ast_path)
        tech = self.file_repo.read_json(tech_path)
        return LegacyCodeEntity(migration_name, ast, tech)
