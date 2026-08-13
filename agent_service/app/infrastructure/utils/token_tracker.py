"""
Token tracking utilities for Agno agent calls.

Usage — three patterns:

  1. Wrapper (preferred — one call does run + track):
       response = agent_run_tracked(agent, prompt, source="doc:technical_doc")

  2. Post-call helper (use when you already have the response):
       response = agent.run(prompt)
       track_tokens(response, source="scanner:kg_builder")

  3. Workflow harvest (call ONCE after workflow.run() in the orchestrator):
       result = await asyncio.to_thread(self.workflow.run, ...)
       ingest_workflow_response(result)

     This automatically persists tokens for every Workflow/Agent/Team
     executor step (scan_workflow, kb_workflow, plan_workflow). Function-
     executor steps (convert_workflow) are not included here — use pattern
     1 or 2 inside those.

All patterns read migration/user context vars automatically and never raise.
"""
import logging
import threading
from typing import Any, Optional

from app.infrastructure.repositories.token_event_repository import save_token_event
from app.infrastructure.utils.migration_context import (
    llm_scope_ctx,
    migration_id_ctx,
    migration_name_ctx,
    migration_run_id_ctx,
)
from app.infrastructure.utils.user_context import current_user

logger = logging.getLogger(__name__)


# ── Low-level helpers ──────────────────────────────────────────────────────────

def _extract_token_counts(response: Any) -> tuple[int, int, int]:
    """Extract (input, output, total) from an Agno RunOutput.metrics object."""
    metrics = getattr(response, "metrics", None)
    if metrics is None:
        return 0, 0, 0
    return (
        int(getattr(metrics, "input_tokens",  0) or 0),
        int(getattr(metrics, "output_tokens", 0) or 0),
        int(getattr(metrics, "total_tokens",  0) or 0),
    )


def _resolve_model_name(response: Any) -> str:
    """Best-effort model name from RunOutput."""
    model = getattr(response, "model", None)
    if model:
        return str(model)
    metrics = getattr(response, "metrics", None)
    if metrics:
        details = getattr(metrics, "details", None) or {}
        for entries in details.values():
            if entries:
                model_id = getattr(entries[0], "id", None)
                if model_id:
                    return str(model_id)
    return ""


def _resolve_source(source: Optional[str]) -> str:
    """Use explicit source, fall back to llm_scope_ctx, then empty string."""
    if source:
        return source
    return llm_scope_ctx.get(None) or ""


def _get_ctx(ctx_var) -> Optional[Any]:
    try:
        return ctx_var.get(None)
    except Exception:
        return None


def _save_in_background(kwargs: dict) -> None:
    """Write the token event on a daemon thread so it never blocks the caller."""
    try:
        save_token_event(**kwargs)
    except Exception as exc:
        logger.debug("Background token event save failed: %s", exc)


def _dispatch_save(
    *,
    source: str,
    input_tokens: int,
    output_tokens: int,
    total_tokens: int,
    agno_run_id: str = "",
    model_name: str = "",
    prompt_name: Optional[str] = None,
    prompt_id: Optional[int] = None,
) -> None:
    """
    Resolve migration/user context and fire a background DB write.
    Shared by track_tokens() and ingest_workflow_response() so both
    use identical persistence logic.
    """
    user = current_user.get(None)

    kwargs = dict(
        migration_id=_get_ctx(migration_id_ctx),
        migration_name=_get_ctx(migration_name_ctx),
        user_id=int(user.id) if user and user.id is not None else None,
        migration_run_id=_get_ctx(migration_run_id_ctx),
        agno_run_id=agno_run_id,
        source=source,
        prompt_name=prompt_name,
        prompt_id=prompt_id,
        model_name=model_name,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
    )

    thread = threading.Thread(target=_save_in_background, args=(kwargs,), daemon=True)
    thread.start()


# ── Public API ─────────────────────────────────────────────────────────────────

def track_tokens(
    response: Any,
    *,
    source: Optional[str] = None,
    prompt_name: Optional[str] = None,
    prompt_id: Optional[int] = None,
) -> None:
    """
    Persist token consumption from an Agno RunOutput to DB.
    Reads migration/user context vars automatically.
    Non-blocking: write is dispatched to a daemon thread.
    Never raises.
    """
    try:
        input_tokens, output_tokens, total_tokens = _extract_token_counts(response)
        if input_tokens == 0 and output_tokens == 0:
            return  # nothing to record

        _dispatch_save(
            source=_resolve_source(source),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            agno_run_id=str(getattr(response, "run_id", None) or ""),
            model_name=_resolve_model_name(response),
            prompt_name=prompt_name,
            prompt_id=prompt_id,
        )
    except Exception as exc:
        logger.debug("track_tokens: unexpected error (ignored): %s", exc)


def ingest_workflow_response(response: Any) -> None:
    """
    Strategy 1 — Agno-native workflow metrics harvest.

    Call ONCE after workflow.run() in agent_orchestrator.py.
    Iterates response.metrics.steps and fires one background DB write per
    step that carried token data (Workflow / Agent / Team executors only).

    Function-executor steps produce no RunMetrics in Agno and are silently
    skipped — cover those with track_tokens() / agent_run_tracked() inside
    the function body.

    Steps covered automatically for migration_workflow:
        scan_workflow          (workflow= executor)
        kb_workflow            (workflow= executor)
        plan_workflow          (workflow= executor)

    Steps NOT covered here — add track_tokens() inside the function:
        convert_workflow               (executor= function)

    Never raises.
    """
    try:
        metrics = getattr(response, "metrics", None)
        if metrics is None:
            logger.debug("[TokenTracker] ingest_workflow_response: no .metrics on response")
            return

        steps: dict = getattr(metrics, "steps", None) or {}
        if not steps:
            logger.debug("[TokenTracker] ingest_workflow_response: metrics.steps is empty")
            return

        ingested = 0
        for step_name, step_metrics in steps.items():
            run_metrics = getattr(step_metrics, "metrics", None)
            if run_metrics is None:
                # Expected for function-executor steps — no LLM metrics attached
                logger.debug(
                    "[TokenTracker] Step '%s' has no RunMetrics (function executor) — skipped",
                    step_name,
                )
                continue

            inp   = int(getattr(run_metrics, "input_tokens",  0) or 0)
            out   = int(getattr(run_metrics, "output_tokens", 0) or 0)
            total = int(getattr(run_metrics, "total_tokens",  0) or 0)

            # Derive total if the field isn't populated by the model backend
            if total == 0 and (inp or out):
                total = inp + out

            if inp == 0 and out == 0:
                logger.debug("[TokenTracker] Step '%s' has zero tokens — skipped", step_name)
                continue

            # Best-effort model name from step RunMetrics.details
            model_name = ""
            details = getattr(run_metrics, "details", None) or {}
            for entries in details.values():
                if entries:
                    model_id = getattr(entries[0], "id", None)
                    if model_id:
                        model_name = str(model_id)
                        break

            # Build a readable source label: "step_name:executor_name"
            executor_name = getattr(step_metrics, "executor_name", "") or ""
            source_label  = f"{step_name}:{executor_name}" if executor_name else step_name

            logger.info(
                "[TokenTracker] Workflow step '%s' (%s/%s) → in=%d out=%d total=%d",
                step_name,
                getattr(step_metrics, "executor_type", "") or "",
                executor_name,
                inp, out, total,
            )

            _dispatch_save(
                source=source_label,
                input_tokens=inp,
                output_tokens=out,
                total_tokens=total,
                model_name=model_name,
            )
            ingested += 1

        logger.info(
            "[TokenTracker] ingest_workflow_response: persisted %d / %d steps",
            ingested, len(steps),
        )

    except Exception as exc:
        logger.debug(
            "[TokenTracker] ingest_workflow_response: unexpected error (ignored): %s", exc
        )


def agent_run_tracked(
    agent: Any,
    prompt: Any,
    *,
    source: Optional[str] = None,
    prompt_name: Optional[str] = None,
    prompt_id: Optional[int] = None,
    **kwargs: Any,
) -> Any:
    """
    Drop-in replacement for agent.run(prompt).
    Runs the agent and tracks token consumption in the background.

    Example:
        response = agent_run_tracked(utility_agent, my_prompt, source="doc:tech_doc")

    All extra kwargs are forwarded to agent.run().
    """
    response = agent.run(prompt, **kwargs)
    track_tokens(
        response,
        source=source or _resolve_agent_source(agent),
        prompt_name=prompt_name,
        prompt_id=prompt_id,
    )
    return response


def _resolve_agent_source(agent: Any) -> str:
    """Derive a readable source string from the agent object when none is given."""
    scope = llm_scope_ctx.get(None)
    if scope:
        return scope
    name = getattr(agent, "name", None) or getattr(agent, "agent_id", None)
    return str(name) if name else "unknown_agent"