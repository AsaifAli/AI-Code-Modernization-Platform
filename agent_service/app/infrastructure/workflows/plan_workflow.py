from agno.agent import Agent
from agno.tools.workflow import WorkflowTools
from agno.workflow.workflow import Workflow
from agno.workflow.step import Step
from agno.workflow.condition import Condition
from agno.workflow.types import StepInput, StepOutput
from pathlib import Path
import json
from agno.run import RunContext
import logging
from app.infrastructure.agents_backend.model_provider import model
from app.application.agents.planning.planning_tools import *
from app.infrastructure.utils.file_utils import get_migration_directory
from app.infrastructure.utils.migration_context_resolver import (
    resolve_migration_name,
    resolve_source_path,
    resolve_target_path,
)
from app.infrastructure.utils.Constants.planning_constants import (
    PlanningLogMessages as PLM,
)

logger = logging.getLogger(__name__)

def _migration_dir(session_state: dict | None = None) -> Path:
    return get_migration_directory(
        migration_name=resolve_migration_name(session_state),
        source_path=resolve_source_path(session_state),
    )

def _has_target_path(run_context: RunContext, step_input: StepInput) -> bool:
    # step_input.session_state is available if agno passes it (newer versions)
    session_state = run_context.session_state or {}
    target_path = resolve_target_path(session_state)
    if not target_path:
        return False
    p = Path(str(target_path))
    return p.exists() and any(p.iterdir())


# ─────────────────────────────────────────────────────────────────── Workflow ────────────────────────────────────────────────────────────────
plan_workflow = Workflow(
    name="Planning Workflow",
    description=(
        "Generates target symbol name, type and file for each source symbol and transformations thet splits large symbols into parts then produce migration plan with goals"
    ),
    debug_mode=True,
    steps=[
        Step(name="get_symbol_module_meta",             description="Fetch data from the KB",                   executor=get_symbol_module_meta),
        Step(name="generate_dependency_plan",           description="Inject dependency file plan entry",        executor=generate_dependency_plan),
        Step(name="generate_symbols_transformation",    description="Generate transformations for each symbol", executor=generate_symbols_transformation),
        Step(name="generate_migration_plan",            description="Generate the overall migration plan",      executor=generate_migration_plan),
    ]
)
