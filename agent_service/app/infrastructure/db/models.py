from sqlalchemy import Column, Integer, String, Text, JSON, DateTime, UniqueConstraint
from sqlalchemy.sql import func
from app.infrastructure.db.db_connection import Base


class MigrationArtifact(Base):
    """Stores JSON artifacts (e.g. response.json) per migration run."""

    __tablename__ = "migration_artifacts"

    id = Column(Integer, primary_key=True, index=True)
    migration_name = Column(String(255), nullable=False, index=True)
    user_id = Column(Integer, nullable=True, index=True)
    type = Column(String(64), nullable=False, index=True)  # e.g. "response", "scanner_output"
    scope = Column(String(64), nullable=False, index=True)  # e.g. "migration"
    payload = Column(JSON, nullable=False)  # the JSON content (dict/list)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Model(Base):
    __tablename__ = "models"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)
    description = Column(Text, nullable=True)

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)


class AgentTask(Base):
    """Persists /v1/teams/run background task status so it survives an
    agent_service restart (previously an in-memory dict in agent_router.py)."""

    __tablename__ = "agent_tasks"

    task_id = Column(String(64), primary_key=True)
    user_id = Column(String(64), nullable=False, index=True)
    status = Column(String(32), nullable=False, index=True)
    result = Column(Text, nullable=True)
    error = Column(Text, nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)


class MigrationLlmTokenEvent(Base):
    """LLM token accounting events; created automatically with the app schema."""

    __tablename__ = "migration_llm_token_events"

    id = Column(Integer, primary_key=True, index=True)
    migration_id = Column(Integer, nullable=True, index=True)
    migration_name = Column(String(255), nullable=True, index=True)
    user_id = Column(Integer, nullable=True, index=True)
    migration_run_id = Column(String(128), nullable=True, index=True)
    agno_run_id = Column(String(128), nullable=True, index=True)
    source = Column(String(256), nullable=True)
    prompt_name = Column(String(200), nullable=True)
    prompt_id = Column(Integer, nullable=True)
    model_name = Column(String(256), nullable=True)
    input_tokens = Column(Integer, nullable=False, default=0)
    output_tokens = Column(Integer, nullable=False, default=0)
    total_tokens = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class MigrationData(Base):
    """Minimal compatibility table used by migration history/listing repositories."""

    __tablename__ = "migration_data"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=True, index=True)
    migration_name = Column(String(255), nullable=False, index=True)
    created_by = Column(Integer, nullable=True)
    updated_by = Column(Integer, nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    __table_args__ = (UniqueConstraint("user_id", "migration_name", name="uq_migration_data_user_name"),)
