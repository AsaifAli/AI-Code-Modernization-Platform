from agno.workflow import Workflow, StepOutput, StepInput
import json
import logging
from pathlib import Path
from app.infrastructure.utils.user_context import current_user
from app.application.agents.conversion.conversion_tools import *
from app.infrastructure.utils.file_utils import get_migration_directory
from app.infrastructure.repositories.json_artifact_repository import (
    fetch_json_artifact as _fetch_artifact,
    get_json_artifact_repository,
)
from app.infrastructure.utils.Agent_helpers.conversion_helper import _conversion_event_helper
from app.infrastructure.utils.Constants.app_constants import ArtifactType, AgentConstants
from app.infrastructure.utils.migration_context import migration_name_ctx
from app.infrastructure.utils.enums.migration_event import MigrationEvent
from app.infrastructure.utils.Constants.migration_workflow import MigrationWorkflowStrings

logger = logging.getLogger(__name__)

_conversion_workflow = Workflow(
    name="Conversion Workflow Pipeline",
    steps=[
        get_symbol_meta_by_id,
        get_source_code,
        get_dependencies,
        generate_new_code,
        save_code_to_kb,
    ]
)


def convert_workflow(step_input: StepInput) -> StepOutput:
    """Load plan file and run conversion workflow for each symbol in the plan."""

    # ── Load plan — DB primary, file fallback ─────────────────────────────
    module_plans = None
    _mig = migration_name_ctx.get("")
    if _mig:
        try:
            module_plans = _fetch_artifact(_mig, ArtifactType.MIGRATION_PLAN)
        except Exception as exc:
            logger.warning("Failed to load migration_plan from DB: %s", exc)

    if module_plans is None:
        migration_dir  = get_migration_directory("", "")
        plan_file_path = migration_dir / "migration_plan.json"
        if not plan_file_path.exists():
            return StepOutput(
                content={"error": f"migration_plan.json not found at {plan_file_path}"},
                success=False,
            )
        with open(plan_file_path, "r", encoding="utf-8") as f:
            module_plans = json.load(f)

    if not isinstance(module_plans, dict) or not module_plans:
        return StepOutput(
            content={"error": "Migration plan is empty; conversion is blocked."},
            success=False,
        )

    symbol_plans = [
        p
        for plan_data in module_plans.values() if isinstance(plan_data, dict)
        for p in (plan_data.get("plans", []) or [])
        if isinstance(p, dict) and p.get("symbol_id") not in {None, "", "dependency_file"}
    ]
    if not symbol_plans:
        logger.error("Conversion blocked: migration plan contains no source-symbol plans")
        return StepOutput(
            content={
                "error": "Migration plan contains no source-symbol plans; conversion is blocked.",
                "converted": 0,
                "failed": 1,
            },
            success=False,
        )

    print(f"Loaded plan: {len(module_plans)} modules")
    # ── Early exit if everything already done ─────────────────────────────
    all_plans = [
        p
        for plan_data in module_plans.values()
        for p in plan_data.get("plans", [])
    ]
    total_plans_overall = len(all_plans)
    already_done = sum(1 for p in all_plans if p.get("migration_status") in {"completed", "error", "dependency_file"})

    if already_done == total_plans_overall:
        logger.info(f"All {total_plans_overall} plans already completed — nothing to convert.")
        return StepOutput(
            content={
                AgentConstants.RESPONSE_MESSAGE: MigrationWorkflowStrings.CONVERSION_WORKFLOW_COMPLETED,
                "converted": 0,
                "skipped":   total_plans_overall,
                "failed":    0,
                "errors":    [],
            },
            success=True,
        )

    # ── Progress setup ─────────────────────────────────────────────────────
    _SKIP_STATUSES = {"completed", "error", "dependency_file"}

    all_plans = [
        p
        for plan_data in module_plans.values()
        for p in plan_data.get("plans", [])
    ]
    total_plans_overall = len(all_plans)
    already_done        = sum(1 for p in all_plans if p.get("migration_status") in _SKIP_STATUSES)
    per_plan_pct        = 100.0 / total_plans_overall if total_plans_overall > 0 else 0
    completed_count     = already_done  # start from already-done so bar is correct on reruns

    results  = []
    errors   = []
    skipped  = []

    completed_plan_ids: set[str] = set()
    failed_plan_ids:    set[str] = set()

    for module_name, plan_data in module_plans.items():
        plans = plan_data.get("plans", [])
        print(f"🔄 Converting module '{module_name}' — {len(plans)} plans")

        for symbol_plan in plans:
            symbol_id  = symbol_plan.get("symbol_id", "unknown")
            plan_id    = symbol_plan.get("plan_id", "")
            status     = symbol_plan.get("migration_status", "pending")
            depends_on = symbol_plan.get("depends_on_plans", []) or []

            # ── Skip sentinel statuses ────────────────────────────────────
            if status in _SKIP_STATUSES:
                label = {
                    "completed":       "already completed",
                    "error":           f"error — {symbol_plan.get('error', '')}",
                    "dependency_file": "dependency file sentinel",
                }.get(status, status)

                logger.info(f"  ⏭  Skipping {symbol_id} ({plan_id}): {label}")

                if status == "error":
                    logger.warning(f"  ⚠️  Skipping error plan: {symbol_id} ({plan_id}) — {symbol_plan.get('error', '')}")
                    skipped.append(plan_id)
                    failed_plan_ids.add(plan_id)
                    continue

                # Terminal plans were already included in completed_count when
                # progress was initialized; do not count them twice.
                completed_plan_ids.add(plan_id)
                skipped.append(plan_id)
                continue

            # ── Skip if any dependency failed ─────────────────────────────
            failed_deps = [d for d in depends_on if d in failed_plan_ids]
            if failed_deps:
                logger.warning(
                    f"  ⏭  Skipping {symbol_id} ({plan_id}) — "
                    f"depends on failed plans: {failed_deps}"
                )
                skipped.append(plan_id)
                failed_plan_ids.add(plan_id)
                completed_count += 1
                continue

            # ── Convert ───────────────────────────────────────────────────
            try:
                print(f"  ▶ Converting symbol: {symbol_id} ({plan_id})")
                run_output = _conversion_workflow.run(input=symbol_plan)

                # Agno can be configured to skip a failed step and continue.
                # Never infer success merely because Workflow.run() returned:
                # inspect the real StepOutput results.
                step_results = getattr(run_output, "step_results", None) or []
                failures = []
                for result in step_results:
                    items = result if isinstance(result, list) else [result]
                    for item in items:
                        if getattr(item, "success", True) is False:
                            step_name = getattr(item, "step_name", None) or "unknown-step"
                            error = getattr(item, "error", None) or getattr(item, "content", None) or "step failed"
                            failures.append(f"{step_name}: {error}")

                if failures:
                    raise RuntimeError("Conversion workflow failed: " + " | ".join(map(str, failures)))

                results.append(plan_id)
                completed_plan_ids.add(plan_id)
                print(f"  ✅ Done: {symbol_id} ({plan_id})")

            except Exception as e:
                logger.error(f"  ❌ Failed: {symbol_id} ({plan_id}) — {e}")
                errors.append({
                    "plan_id":   plan_id,
                    "symbol_id": symbol_id,
                    "error":     str(e),
                })
                failed_plan_ids.add(plan_id)
                completed_count += 1
                continue

            # ── Unified progress update ────────────────────────────────────
            completed_count += 1

            progress_pct = min(
                100,
                round(completed_count * per_plan_pct)
            )

            logger.info(
                f"[ConversionProgress] {symbol_id} ({plan_id}) — "
                f"{completed_count}/{total_plans_overall} — {progress_pct}%"
            )

            try:
                user = current_user.get()
                _conversion_event_helper.send_progress(
                    percent=progress_pct,
                    message=f"Processed {completed_count}/{total_plans_overall} plans",
                    user=user,
                    msg_group_id=MigrationEvent.MIGRATION_PROGRESS,
                    plan_id=plan_id,
                )
            except Exception:
                pass

    # ── Persist updated plan statuses back to DB + file ───────────────────
    for mod_data in module_plans.values():
        for entry in mod_data.get("plans", []):
            pid = entry.get("plan_id", "")
            if pid in failed_plan_ids and entry.get("migration_status") not in ("error", "dependency_file"):
                entry["migration_status"] = "error"
            elif pid in completed_plan_ids and entry.get("migration_status") == "pending":
                entry["migration_status"] = "completed"
            # already-terminal statuses (dependency_file, pre-existing error) are left untouched

    migration_dir  = get_migration_directory("", "")
    plan_file_path = migration_dir / "migration_plan.json"
    try:
        with open(plan_file_path, "w", encoding="utf-8") as f:
            json.dump(module_plans, f, indent=2, ensure_ascii=False)
        logger.info("Updated migration_plan.json with latest statuses")
    except Exception as exc:
        logger.warning("Failed to write updated migration_plan.json: %s", exc)

    if _mig:
        try:
            try:
                _plan_user    = current_user.get()
                _plan_user_id = _plan_user.id if _plan_user else None
            except Exception:
                _plan_user_id = None
            get_json_artifact_repository().save_json_artifact(
                _mig, ArtifactType.MIGRATION_PLAN, module_plans, user_id=_plan_user_id
            )
            logger.info("Persisted updated migration_plan to DB artifact store")
        except Exception as exc:
            logger.warning("Failed to persist updated migration_plan to DB: %s", exc)

    # ─────────────────────────────────────────────────────────────────────
    logger.info(
        f"Conversion complete — "
        f"converted: {len(results)}, "
        f"skipped: {len(skipped)}, "
        f"failed: {len(errors)}"
    )

    return StepOutput(
        content={
            AgentConstants.RESPONSE_MESSAGE: (
                MigrationWorkflowStrings.CONVERSION_WORKFLOW_COMPLETED
                if not errors
                else "Conversion completed with errors."
            ),
            "converted": len(results),
            "skipped":   len(skipped),
            "failed":    len(errors),
            "errors":    errors,
        },
        success=not errors,
    )