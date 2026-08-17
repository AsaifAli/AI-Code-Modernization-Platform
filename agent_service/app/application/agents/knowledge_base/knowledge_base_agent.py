from app.infrastructure.agents_backend.qdrant_knowledge import QdrantKnowledgeBase, _collection_name

source_knowledge: QdrantKnowledgeBase | None = None
target_knowledge: QdrantKnowledgeBase | None = None


def init_knowledge_bases() -> None:
    global source_knowledge, target_knowledge
    source_knowledge = QdrantKnowledgeBase(_collection_name("source"))
    target_knowledge = QdrantKnowledgeBase(_collection_name("target"))

# Legacy agent_setup imports this name, even though the current KB work is
# performed through the workflow/tool layer. Keep the symbol to preserve the
# public import contract without adding another local vector-store object.
kb_agent = None
