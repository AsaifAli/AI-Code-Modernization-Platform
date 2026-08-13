"""
Repository for LLM token consumption events.
Inserts rows into public.migration_llm_token_events.
Fire-and-forget: all errors are logged, never re-raised.
"""
import logging
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.infrastructure.db.db_connection import engine

logger = logging.getLogger(__name__)


def save_token_event(
    *,
    migration_id: Optional[int],
    migration_name: Optional[str],
    user_id: Optional[int],
    migration_run_id: Optional[str],
    agno_run_id: Optional[str],
    source: Optional[str],
    prompt_name: Optional[str],
    prompt_id: Optional[int],
    model_name: Optional[str],
    input_tokens: int,
    output_tokens: int,
    total_tokens: int,
) -> None:
    """Insert one token-consumption event. Silently skips if DB is unavailable."""
    if engine is None:
        return
    try:
        with Session(engine) as session:
            session.execute(
                text(
                    """
                    INSERT INTO public.migration_llm_token_events
                        (migration_id, migration_name, user_id, migration_run_id,
                         agno_run_id, source, prompt_name, prompt_id, model_name,
                         input_tokens, output_tokens, total_tokens)
                    VALUES
                        (:migration_id, :migration_name, :user_id, :migration_run_id,
                         :agno_run_id, :source, :prompt_name, :prompt_id, :model_name,
                         :input_tokens, :output_tokens, :total_tokens)
                    """
                ),
                {
                    "migration_id": migration_id,
                    "migration_name": migration_name,
                    "user_id": user_id,
                    "migration_run_id": migration_run_id,
                    "agno_run_id": agno_run_id,
                    "source": (source or "")[:256],
                    "prompt_name": (prompt_name or "")[:200],
                    "prompt_id": prompt_id,
                    "model_name": (model_name or "")[:256],
                    "input_tokens": int(input_tokens or 0),
                    "output_tokens": int(output_tokens or 0),
                    "total_tokens": int(total_tokens or 0),
                },
            )
            session.commit()
    except Exception as exc:
        logger.warning("Failed to save token event (source=%s): %s", source, exc)
