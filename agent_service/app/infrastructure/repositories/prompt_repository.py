from app.infrastructure.db.prompts import Prompt
from app.infrastructure.db.db_connection import SessionLocal, MODEL_ID

import logging
logger = logging.getLogger(__name__)

class PromptRepository:
    def __init__(self, db_session):
        self.db_session = db_session

    def get_prompt(self, name: str, model_id: int = None):
        """Fetch a prompt by name and optionally by model_id."""
        try:
            query = self.db_session.query(Prompt).filter(Prompt.prompt_name == name)
            if model_id is not None:
                query = query.filter(Prompt.model_id == model_id)
            elif MODEL_ID is not None:
                query = query.filter(Prompt.model_id == MODEL_ID)
            
            prompt_obj = query.first()
            return prompt_obj
        except Exception as e:
            raise Exception(f"DB error while fetching prompt '{name}': {str(e)}")


def get_prompt_repository():
    """
    Helper function to create a PromptRepository instance with a database session.
    Returns a tuple of (repository, db_session) for proper session management.
    """
    if SessionLocal is None:
        raise Exception("Database not configured. Cannot create prompt repository.")
    
    db = SessionLocal()
    repo = PromptRepository(db)
    return repo, db


def fetch_prompt_from_db(prompt_name: str, model_id: int = None):
    """
    Global helper function to fetch a prompt from the database.
    Handles session creation, prompt fetching, validation, and session closure.
    """
    if SessionLocal is None:
        return None
    
    db = SessionLocal()
    try:
        repo = PromptRepository(db)
        prompt_obj = repo.get_prompt(prompt_name, model_id=model_id)
        
        if not prompt_obj or not prompt_obj.is_active:
            logger.warning(f"Prompt '{prompt_name}' not found or Wrong (model_id={model_id or MODEL_ID})")
            return None
        
        return prompt_obj
    except Exception as e:
        logger.error("fetch_prompt_from_db failed for %s (model_id=%s): %s", prompt_name, model_id or MODEL_ID, e)
        return None
    finally:
        db.close()


