from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.infrastructure.db.db_connection import Base
from app.infrastructure.db.db_connection import Base, MODEL_ID
class Prompt(Base):
    __tablename__ = "prompts"

    id = Column(Integer, primary_key=True, index=True)

    prompt_type_id = Column(
        Integer, 
        ForeignKey("prompt_types.id", ondelete="CASCADE"),
        nullable=False
    )

    # prompt_type = relationship("PromptType")

    model_id = Column(
        Integer,
        ForeignKey("models.id", ondelete="SET NULL"),
        nullable=True,
        default=MODEL_ID  # Loaded from .env
    )
    # model = relationship("Model")

    prompt_name = Column(String(200), nullable=False, unique=True)
    prompt_content = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    version = Column(String(20), default="1.0")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

