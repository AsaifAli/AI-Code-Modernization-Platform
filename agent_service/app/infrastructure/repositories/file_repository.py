import json
from pathlib import Path
from app.domain.interfaces.i_file_repository import IFileRepository


class FileRepository(IFileRepository):
    """Concrete repository handling local file system I/O."""

    def read_json(self, path: str):
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def write_json(self, path: str, data):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def write_text(self, path: str, content: str):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def create_directory(self, path: str):
        Path(path).mkdir(parents=True, exist_ok=True)
