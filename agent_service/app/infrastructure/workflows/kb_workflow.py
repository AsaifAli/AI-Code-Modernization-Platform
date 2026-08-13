from agno.agent import Agent
from agno.tools.workflow import WorkflowTools
from agno.workflow.workflow import Workflow
from agno.workflow.step import Step
from pathlib import Path
from agno.run import RunContext
from agno.workflow.types import StepInput, StepOutput
from app.infrastructure.utils.file_utils import get_migration_directory
from app.application.agents.knowledge_base.knowledge_base_tools import load_json_to_knowledge
from app.infrastructure.utils.migration_context_resolver import (
    resolve_migration_name,
    resolve_source_path,
    resolve_target_path,
)
# ─────────────────────────────────────────────────────────────────── Workflow ───────────────────────────────────────────────────────────────────
kb_workflow = Workflow(
    name="Knowledge Base Workflow",
    description="Stores the knowledge graph into the vector knowledge base",
    steps=[Step(name="load_json_to_knowledge",    description=("Stores the knowledge graph into the knowledge base for both source and target"),  executor=load_json_to_knowledge)],)