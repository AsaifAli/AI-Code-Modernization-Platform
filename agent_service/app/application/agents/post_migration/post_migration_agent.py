import json

from agno.agent import Agent
from agno.tools.workflow import WorkflowTools
from agno.workflow.workflow import Workflow
from agno.workflow.step import Step
from agno.workflow.types import StepInput, StepOutput

from app.infrastructure.agents_backend.model_provider import model
from app.infrastructure.utils.migration_context_resolver import resolve_migration_name
from app.application.agents.post_migration.post_migration_tools import (
    run_post_migration_analysis_impl,
)


def _run_post_migration(step_input: StepInput) -> StepOutput:
    session_state = getattr(step_input, "session_state", None) or {}
    migration_name = resolve_migration_name(session_state)
    # The conversion workflow writes to migration_dir/"Migrated Code".
    # Let the post-migration helper resolve the canonical output location so
    # target_path from the request cannot accidentally point at the source tree.
    result = run_post_migration_analysis_impl(
        migration_name=migration_name,
        migrated_code_path=None,
        persist=True,
    )
    try:
        parsed = json.loads(result) if isinstance(result, str) else result
    except Exception:
        parsed = {}
    status = parsed.get("status") if isinstance(parsed, dict) else None
    blocked = status in {"blocked", "not_ready"}
    # Keep nested workflow/executor boundaries string-safe. The actual status
    # lives on StepOutput.success/stop rather than inside a dict expected to
    # behave like a workflow result object.
    return StepOutput(
        content=result if isinstance(result, str) else json.dumps(parsed, ensure_ascii=False),
        success=not blocked,
        stop=blocked,
        error="Post-migration release gate failed" if blocked else None,
    )


post_migration_workflow = Workflow(
    name="Post Migration Workflow",
    description="Analyze migrated codebase and generate post-migration deliverables",
    steps=[
        Step(
            name="Post Migration Analysis",
            description="Run target scan and report/showcase generation",
            executor=_run_post_migration,
        ),
    ],
)


post_migration_agent = Agent(
    name="Post Migration Agent",
    model=model,
    markdown=True,
    instructions=(
        "Run the post migration workflow immediately. "
        "Always call run_workflow using the exact `input` argument name."
    ),
    tools=[WorkflowTools(workflow=post_migration_workflow)],
    tool_choice={"type": "function", "function": {"name": "run_workflow"}},
    tool_call_limit=1,
    debug_mode=True,
    description="Post-migration analysis agent for migrated codebase artifacts.",
)

