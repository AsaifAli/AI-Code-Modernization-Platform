from agno.agent import Agent
from agno.tools.workflow import WorkflowTools
from agno.workflow.workflow import Workflow
from agno.workflow.step import Step
from agno.workflow.condition import Condition
from agno.workflow.types import StepInput, StepOutput
from pathlib import Path
from agno.run import RunContext
from app.infrastructure.utils.file_utils import get_migration_directory
from app.infrastructure.agents_backend.model_provider import model
from app.application.agents.scanner.scanner_tools import *
from app.infrastructure.utils.migration_context_resolver import (
    resolve_migration_name,
    resolve_source_path,
    resolve_target_path,
)

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
scan_workflow = Workflow(
    name="Scanner Workflow",
    steps=[
        Step(name="generate_project_graph",   executor=generate_project_graph,    description="Generate project graph and non-convertible files"),
        Step(name="generate_symbol_roles",    executor=generate_symbol_roles,     description="Generate symbol-wise roles and summaries"),
        Step(name="generate_tech_data",       executor=generate_tech_data,        description="Detect tech stack from analyzer and project graph"),
        Step(name="generate_module_labelling",executor=generate_module_labelling, description="Detect and label modules"),
        Step(name="generate_complexity",      executor=generate_complexity,       description="Compute symbol and module complexity scores"),
        Step(name="generate_knowledge_graph", executor=generate_knowledge_graph,  description="Assemble and persist final knowledge graph"),
    ],
)