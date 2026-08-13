from agno.knowledge.knowledge import Knowledge
from agno.vectordb.lancedb import LanceDb, SearchType
from agno.db.sqlite import SqliteDb
from app.infrastructure.agents_backend.model_provider import model_embedder
from app.infrastructure.utils.file_utils import get_migration_directory

source_knowledge: Knowledge = None
target_knowledge: Knowledge = None

def init_knowledge_bases() -> None:
    global source_knowledge, target_knowledge
    base = get_migration_directory("", "")
    base.mkdir(parents=True, exist_ok=True)
    source_knowledge = Knowledge(
        contents_db=SqliteDb(db_file=str(base / "source_knowledge.db")),
        vector_db=LanceDb(
            uri=str(base / "lancedb"),
            table_name="source_table",
            search_type=SearchType.hybrid,
            embedder=model_embedder,
        ),
    )
    target_knowledge = Knowledge(
        contents_db=SqliteDb(db_file=str(base / "target_knowledge.db")),
        vector_db=LanceDb(
            uri=str(base / "lancedb"),
            table_name="target_table",
            search_type=SearchType.hybrid,
            embedder=model_embedder,
        ),
    )