from sqlalchemy import Column, Integer, String, Text
from app.infrastructure.db.db_connection import Base

class PromptType(Base):
    __tablename__ = "prompt_types"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)
    description = Column(Text, nullable=True)