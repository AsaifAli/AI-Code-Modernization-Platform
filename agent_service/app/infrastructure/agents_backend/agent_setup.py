# app/infrastructure/agents_backend/agent_setup.py

from app.infrastructure.agents_backend.model_provider import model
from app.application.agents.scanner.scanner_agent import scanner_agent
from app.application.agents.conversion.conversion_agent import conversion_agent
from app.application.agents.planning.planning_agent import planning_agent
from app.application.agents.knowledge_base.knowledge_base_agent import kb_agent
from app.application.agents.chat.chat_agent import chat_agent
from app.application.agents.post_migration.post_migration_agent import post_migration_agent

__all__ = [
    "model",
    "scanner_agent",
    "conversion_agent",
    "planning_agent",
    "kb_agent",
    "chat_agent",
    "post_migration_agent",
]
