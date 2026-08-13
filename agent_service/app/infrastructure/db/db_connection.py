"""
Database Connection Module
Consolidated database connection for the application.
This file should be placed in: app/infrastructure/db/db_connection.py
"""
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv
from app.infrastructure.utils.Constants.validation_messages import ValidationMessages as VM
# Load environment variables from .env file
load_dotenv()

# Read DB credentials from environment variables
# Prefer a complete DATABASE_URL when supplied (for managed/cloud Postgres).
# Fall back to split DB_* settings for the local Docker Compose stack.
DATABASE_URL = os.getenv("DATABASE_URL")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME")
_MODEL_ID_RAW = os.getenv("MODEL_ID")
MODEL_ID = int(_MODEL_ID_RAW) if _MODEL_ID_RAW else None

if not DATABASE_URL and not all([DB_USER, DB_PASSWORD, DB_NAME]):
    import warnings
    warnings.warn(
        VM.DB_CREDENTIALS_NOT_CONFIGURED,
        UserWarning
    )

if not DATABASE_URL and all([DB_USER, DB_PASSWORD, DB_NAME]):
    DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

if DATABASE_URL:
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,  # Verify connections before using
        echo=False  # Set to True for SQL query logging
    )
else:
    engine = None

if engine:
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
else:
    SessionLocal = None

# Base class for declarative models
Base = declarative_base()

def get_db():
    """
    Dependency function to get database session.
    Use this in FastAPI route dependencies.
    
    Example:
        @router.get("/items")
        def get_items(db: Session = Depends(get_db)):
            ...
    """
    if SessionLocal is None:
        raise RuntimeError(VM.DB_NOT_CONFIGURED_FOR_SESSION)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    """Initialize database tables only. Prompts and prompt types should be manually inserted."""
    if engine is None:
        raise RuntimeError(VM.DB_NOT_CONFIGURED_FOR_INIT)
    
    from app.infrastructure.db.prompt_types import PromptType
    from app.infrastructure.db.prompts import Prompt
    from app.infrastructure.db.models import Model, User, MigrationArtifact, AgentTask, MigrationLlmTokenEvent, MigrationData
    
    Base.metadata.create_all(bind=engine)