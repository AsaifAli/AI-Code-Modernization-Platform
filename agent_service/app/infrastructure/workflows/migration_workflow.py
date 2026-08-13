import logging
from pathlib import Path
from agno.workflow.workflow import Workflow
from agno.workflow.step import Step
from agno.workflow.types import StepInput, StepOutput
from app.infrastructure.utils.migration_context import (
    migration_name_ctx,
    source_path_ctx,
)
from app.infrastructure.utils.file_utils import get_migration_directory

logger = logging.getLogger(__name__)

from app.infrastructure.workflows.convert_workflow import convert_workflow
from app.infrastructure.workflows.kb_workflow import kb_workflow
from app.infrastructure.workflows.plan_workflow import plan_workflow
from app.infrastructure.workflows.scan_workflow import scan_workflow
from app.application.agents.post_migration.post_migration_agent import _run_post_migration


# ─────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────

def _migration_dir() -> Path:
    return get_migration_directory(
        migration_name=migration_name_ctx.get(""),
        source_path=source_path_ctx.get(""),
    )


# ─────────────────────────────────────────────────────────────
# VERIFICATION GATES
# ─────────────────────────────────────────────────────────────

def verify_source_scan(step_input: StepInput) -> StepOutput:
    file_path = _migration_dir() / "knowledge_graph.json"
    missing = ["knowledge_graph.json"] if not file_path.exists() else []
    if missing:
        return StepOutput(content=f"Scanner incomplete — missing: {missing}", success=False)
    return StepOutput(content="✅ Source scan verified", success=True)


def verify_plan_output(step_input: StepInput) -> StepOutput:
    migration_dir = _migration_dir()
    plan_path = migration_dir / "migration_plan.json"
    if not plan_path.exists():
        return StepOutput(
            content="❌ Critical file missing: migration_plan.json — workflow cannot continue",
            success=False,
        )

    try:
        import json
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        if not isinstance(plan, dict):
            raise ValueError("migration_plan.json must contain an object")
        symbol_plans = []
        for module_data in plan.values():
            if not isinstance(module_data, dict):
                continue
            for item in module_data.get("plans", []) or []:
                if isinstance(item, dict) and item.get("symbol_id") not in {None, "", "dependency_file"}:
                    symbol_plans.append(item)
        if not symbol_plans:
            return StepOutput(
                content={
                    "status": "failed",
                    "error": "Migration plan contains no source-symbol plans. Conversion and release packaging are blocked.",
                },
                success=False,
            )
        graph = json.loads((_migration_dir() / "knowledge_graph.json").read_text(encoding="utf-8"))
        source_symbol_ids = {
            symbol.get("symbol_id")
            for symbol in graph.get("project_graph", {}).get("symbols", [])
            if isinstance(symbol, dict) and symbol.get("symbol_id")
        }
        covered_symbol_ids = {
            covered_id
            for item in symbol_plans
            for covered_id in item.get("covered_symbol_ids", [item.get("symbol_id")])
            if covered_id
        }
        missing_symbol_ids = source_symbol_ids - covered_symbol_ids
        if missing_symbol_ids:
            return StepOutput(
                content={
                    "status": "failed",
                    "error": "Migration plan omits source symbols; conversion is blocked: "
                    + ", ".join(sorted(missing_symbol_ids)),
                },
                success=False,
            )
    except Exception as exc:
        return StepOutput(
            content={"status": "failed", "error": f"Invalid migration plan: {exc}"},
            success=False,
        )

    return StepOutput(content={"status": "ok", "symbol_plan_count": len(symbol_plans)}, success=True)


# ─────────────────────────────────────────────────────────────
# WORKFLOW
# ─────────────────────────────────────────────────────────────

migration_workflow = Workflow(
    name="Migration Workflow",
    description="Code migration workflow",
    steps=[
        # Step 1 — Scan source code → produces knowledge_graph.json
        Step(
            name="scan_workflow",
            workflow=scan_workflow,
        ),
        # Step 2 — Gate: ensure knowledge_graph.json was produced
        Step(
            name="Verify Scan Output",
            executor=verify_source_scan,
        ),
        # Step 3 — Build knowledge base from scanner output
        Step(
            name="kb_workflow",
            workflow=kb_workflow,
        ),
        # Step 4 — Generate migration plan
        Step(
            name="plan_workflow",
            workflow=plan_workflow,
        ),
        # Step 5 — Gate: ensure migration_plan.json exists
        Step(
            name="Verify Plan Complete",
            description="Confirm migration_plan.json exists before proceeding",
            executor=verify_plan_output,
        ),
        # Step 6 — Convert source code to target
        Step(
            name="convert_workflow",
            executor=convert_workflow,
        ),
        # Step 7 — Engineering gate: lint, test, build, AI-assisted repair loop,
        # target scan/reporting and CI bootstrap. Packaging occurs only after
        # this workflow returns.
        Step(
            name="post_migration_workflow",
            description="Run post-migration validation, autonomous repair, and release gating.",
            executor=_run_post_migration,
        ),
    ],
)
