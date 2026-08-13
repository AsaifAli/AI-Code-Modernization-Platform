import json
import math
import logging
from pathlib import Path
from typing import Optional, Dict, Any
from dotenv import load_dotenv
from app.domain.interfaces.i_json_artifact_repository import IJsonArtifactRepository
from app.domain.interfaces.i_migration_scan_result_repository import (
    IMigrationScanResultRepository,
)
from agno.workflow.step import Step, StepInput, StepOutput
from app.infrastructure.utils.Constants.app_constants import Constants
from app.infrastructure.utils.enums.msg_group import MsgGroup
from app.infrastructure.utils.user_context import current_user
from app.infrastructure.utils.enums.migration_event import MigrationEvent
from app.infrastructure.utils.Constants.agent_event import AgentEventMessages
from app.infrastructure.utils.Constants.app_constants import MigrationScope, ArtifactType
from app.infrastructure.repositories.migration_scan_result_repository import get_migration_scan_result_repository
from app.infrastructure.repositories.json_artifact_repository import (
    get_json_artifact_repository,
    SCOPE_SOURCE,
    SCOPE_TARGET,
)
from app.infrastructure.utils.Agent_helpers.scanner_helper import *
from app.infrastructure.repositories.prompt_repository import fetch_prompt_from_db
from app.infrastructure.utils.file_utils import get_migration_directory, read_json_file
from app.infrastructure.utils.Constants.validation_messages import ValidationMessages as VM
from app.infrastructure.utils.scanner_output import extract_migration_data,generate_full_migration_response
from app.infrastructure.utils.migration_context import migration_name_ctx,source_path_ctx,target_language_ctx,target_path_ctx,migration_id_ctx
load_dotenv()
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

_json_artifact_repo: Optional[IJsonArtifactRepository] = None
_migration_scan_repo: Optional[IMigrationScanResultRepository] = None

__all__ = ['generate_project_graph','generate_symbol_roles','generate_tech_data','generate_module_labelling','generate_complexity','generate_knowledge_graph']


def configure_scanner_repositories(
    *,
    json_artifact_repo: Optional[IJsonArtifactRepository] = None,
    migration_scan_repo: Optional[IMigrationScanResultRepository] = None,
) -> None:
    """Configure repository dependencies for scanner tools (for DI/testing)."""
    global _json_artifact_repo, _migration_scan_repo
    if json_artifact_repo is not None:
        _json_artifact_repo = json_artifact_repo
    if migration_scan_repo is not None:
        _migration_scan_repo = migration_scan_repo


def _get_json_artifact_repo() -> IJsonArtifactRepository:
    global _json_artifact_repo
    if _json_artifact_repo is None:
        _json_artifact_repo = get_json_artifact_repository()
    return _json_artifact_repo


def _get_migration_scan_repo() -> IMigrationScanResultRepository:
    global _migration_scan_repo
    if _migration_scan_repo is None:
        _migration_scan_repo = get_migration_scan_result_repository()
    return _migration_scan_repo


# ── Step 1: Project Graph ─────────────────────────────────────────────────
def generate_project_graph(step_input: StepInput) -> StepOutput:
    """
    Step 1 — Generates project graph (syntactic AST) and non-convertible files list.
    Input  : source_path string (original workflow input via step_input.input)
    Output : JSON string {"project_graph": {}, "non_convertible": [], 
                          "source_project_info": {}, "primary_language": ""}
    """
    legacy_code_step_id      = AgentEventMessages.LEGACY_CODE_STEP_ID
    legacy_code_step_name    = AgentEventMessages.LEGACY_CODE_STEP_NAME
    legacy_code_msg_group_id = MigrationEvent.LEGACY_CODE_ANALYSIS
    user = None
    source_path = step_input.input
    if not source_path:
        raise ValueError(VM.SOURCE_PATH_REQUIRED)
    try:
        user = current_user.get()
        _notify_scanner_start(user, AgentEventMessages.RUNNING_ADVANCED_SCANNER)
        _send_step_start(legacy_code_step_id, legacy_code_step_name, user, legacy_code_msg_group_id)
        _send_step_description(legacy_code_step_id, legacy_code_step_name, user, legacy_code_msg_group_id)
        _send_step_log(legacy_code_step_id, AgentEventMessages.SCANNER_AGENT_INITIALIZED, user, legacy_code_msg_group_id)
        _send_step_log(legacy_code_step_id, AgentEventMessages.ANALYZING_SOURCE_FILES, user, legacy_code_msg_group_id)

        migration_dir = get_migration_directory("", "")
        migration_dir.mkdir(parents=True, exist_ok=True)
        knowledge_graph_file = migration_dir / "knowledge_graph.json"

        # Return cached result if already complete
        if knowledge_graph_file.exists():
            cached_data = read_json_file(str(knowledge_graph_file))
            cached_pg = cached_data.get("project_graph", {})
            cached_symbols = cached_pg.get("symbols", [])
            cached_files = cached_pg.get("files", [])
            if cached_symbols or cached_files:
                out = {
                    "project_graph":       cached_pg,
                    "non_convertible":     cached_data.get("non_convertible_files", []),
                    "source_project_info": {},
                    "primary_language":    cached_data.get("tech_data", {}).get("language", "unknown"),
                    "skipped":             True,
                }
                logger.info(
                    f"[Step 1] Loaded from cache — "
                    f"files={len(cached_files)}, symbols={len(cached_symbols)}"
                )
                return StepOutput(
                    step_name="generate_project_graph",
                    content=json.dumps(out, default=str),
                    success=True,
                )
            else:
                logger.warning("[Step 1] Cache exists but has no symbols/files — re-scanning")
                knowledge_graph_file.unlink(missing_ok=True)
                # Also clear stale planning outputs so Condition gate works correctly
                for stale in "migration_plan.json":
                    stale_file = migration_dir / stale
                    if stale_file.exists():
                        stale_file.unlink(missing_ok=True)
                        logger.warning(f"[Step 1] Removed stale planning file: {stale}")

        source_path_obj      = Path(source_path)
        source_project_info  = _analyze_project(str(source_path_obj))
        non_convertible      = _get_or_create_non_convertible_files(migration_dir, source_path_obj)
        primary_language     = _detect_primary_language(source_project_info, source_path_obj, non_convertible)
        project_graph        = _generate_or_load_project_graph(
            migration_dir=migration_dir,
            source_path_obj=source_path_obj,
            non_convertible=non_convertible,
            primary_language=primary_language,
        )

        out = {
            "project_graph":       project_graph,
            "non_convertible":     list(non_convertible),
            "source_project_info": source_project_info,
            "primary_language":    primary_language,
        }
        logger.info(
            f"[Step 1] Done — files={len(project_graph.get('files', []))}, "
            f"symbols={len(project_graph.get('symbols', []))}, "
            f"non_convertible={len(non_convertible)}"
        )
        return StepOutput(
            step_name="generate_project_graph",
            content=json.dumps(out, default=str),
            success=True,
        )

    except Exception as e:
        logger.error(f"[Step 1] Failed: {e}")
        if user:
            _send_step_error(
                legacy_code_step_id, legacy_code_step_name,
                AgentEventMessages.ERROR_LEGACY_CODE_ANALYSIS.format(error=str(e)),
                user, legacy_code_msg_group_id,
            )
        return StepOutput(step_name="generate_project_graph", content=str(e), success=False, error=str(e))


# ── Step 2: Symbol roles & summaries ─────────────────────────────────────
def generate_symbol_roles(step_input: StepInput) -> StepOutput:
    """
    Step 2 — Generates symbol-wise roles and summaries via LLM batching.
    Input  : JSON output from run_step1_project_graph (via get_step_content)
    Output : JSON string {"project_graph": {}} with role+summary on every symbol
    """
    try:
        raw = step_input.get_step_content("generate_project_graph") or "{}"
        step1 = json.loads(raw)
        if step1.get("skipped"):
            return StepOutput(
                step_name="generate_symbol_roles",
                content=json.dumps({"project_graph": step1.get("project_graph", {}), "skipped": True}, default=str),
                success=True,
            )
        project_graph    = step1.get("project_graph", {})
        primary_language = step1.get("primary_language", "unknown")
        source_path      = step_input.input or ""

        symbols = project_graph.get("symbols", [])
        needs_annotation = symbols and any(
            not s.get("role") or not s.get("summary") for s in symbols
        )
        if needs_annotation:
            semantic_results = _process_semantic_ir_batches(
                all_items=symbols,
                language=primary_language,
                batch_size=100,
                base_path=Path(source_path) if source_path else None,
            )
            for idx, sym in enumerate(symbols):
                if idx < len(semantic_results):
                    if not sym.get("role"):
                        sym["role"] = semantic_results[idx].get("role", "")
                    if not sym.get("summary"):
                        sym["summary"] = semantic_results[idx].get("summary", "")
            project_graph["symbols"] = symbols
            logger.info(f"[Step 2] Done — annotated {len(symbols)} symbols")
        else:
            logger.info("[Step 2] Skipped — all symbols already have role and summary")

        return StepOutput(
            step_name="generate_symbol_roles",
            content=json.dumps({"project_graph": project_graph}, default=str),
            success=True,
        )

    except Exception as e:
        logger.error(f"[Step 2] Failed: {e}")
        return StepOutput(step_name="generate_symbol_roles", content=str(e), success=False, error=str(e))


# ── Step 3: Tech Data ─────────────────────────────────────────────────────
def generate_tech_data(step_input: StepInput) -> StepOutput:
    """
    Step 3 — Detects tech stack (language, framework, architecture, build tool).
    Input  : JSON outputs from Step 1 and Step 2 (via get_step_content)
    Output : JSON string {"tech": {}}
    """
    try:
        step1 = json.loads(step_input.get_step_content("generate_project_graph") or "{}")
        if step1.get("skipped"):
            cached = read_json_file(str(get_migration_directory("", "") / "knowledge_graph.json"))
            return StepOutput(
                step_name="generate_tech_data",
                content=json.dumps({"tech": cached.get("tech_data", {}), "skipped": True}, default=str),
                success=True,
            )
        step2 = json.loads(step_input.get_step_content("generate_symbol_roles") or "{}")

        project_graph       = step2.get("project_graph") or step1.get("project_graph", {})
        source_project_info = step1.get("source_project_info", {})
        primary_language    = step1.get("primary_language", "unknown")
        source_path         = step_input.input or ""

        migration_dir = get_migration_directory("", "")

        tech = _detect_tech_stack(
            migration_dir=migration_dir,
            source_path_obj=Path(source_path),
            project_graph=project_graph,
            source_project_info=source_project_info,
            primary_language=primary_language,
        )
        logger.info(
            f"[Step 3] Done — language={tech.get('language')}, "
            f"framework={tech.get('framework')}, arch={tech.get('architecture')}"
        )
        return StepOutput(
            step_name="generate_tech_data",
            content=json.dumps({"tech": tech}, default=str),
            success=True,
        )

    except Exception as e:
        logger.error(f"[Step 3] Failed: {e}")
        return StepOutput(step_name="generate_tech_data", content=str(e), success=False, error=str(e))


# ── Step 4: Module detection & labelling ───────────────────────
def generate_module_labelling(step_input: StepInput) -> StepOutput:
    """
    Step 4 (optional) — Groups symbols into modules and labels each via LLM.
    Input  : project_graph from Step 2 (via get_step_content)
    Output : JSON string {"project_graph": {}} with modules dict populated
    """
    try:
        step2 = json.loads(step_input.get_step_content("generate_symbol_roles") or "{}")
        if step2.get("skipped"):
            return StepOutput(
                step_name="generate_module_labelling",
                content=json.dumps({"project_graph": step2.get("project_graph", {}), "skipped": True}, default=str),
                success=True,
            )
        project_graph = step2.get("project_graph", {})
        symbols       = project_graph.get("symbols", [])

        # WITH THIS:
        if not symbols:
            logger.info("[Step 4] Skipped — no symbols to group")
            return StepOutput(
                step_name="generate_module_labelling",
                content=json.dumps({"project_graph": project_graph}, default=str),
                success=True,
            )

        # If modules are already labelled (e.g. from Leiden in the AST pipeline),
        # preserve them — path-based grouping would collapse multi-module projects
        # into one coarse group when all symbols share a single module path.
        existing_modules = project_graph.get("modules")
        already_labelled = (
            isinstance(existing_modules, dict)
            and bool(existing_modules)
            and all(
                isinstance(v, dict) and (v.get("role") or v.get("summary"))
                for v in existing_modules.values()
            )
        )
        if already_labelled:
            logger.info(
                f"[Step 4] Skipped — {len(existing_modules)} labelled modules "
                f"already present from AST pipeline"
            )
            return StepOutput(
                step_name="generate_module_labelling",
                content=json.dumps({"project_graph": project_graph}, default=str),
                success=True,
            )

        _module_cfg = {
            "schema": {
                "sym_name":    "name",
                "sym_role":    "role",
                "sym_summary": "summary",
            },
            "label_key_name":    "module_name",
            "label_key_summary": "summary",
            "label_key_role":    "role",
            "label_key_symbols": "symbols",
        }

        module_groups: Dict[str, list] = {}
        for sym in symbols:
            key = sym.get("module") or sym.get("file_path", "unknown")
            module_groups.setdefault(key, []).append(sym)

        labelled_modules: Dict[str, Any] = {}
        for _key, group_syms in module_groups.items():
            result   = generate_module_label(community_symbols=group_syms, cfg=_module_cfg)
            mod_name = result.get("module_name", _key)
            labelled_modules[mod_name] = {
                "role":      result.get("role", ""),
                "summary":   result.get("summary", ""),
                "complexity": 0.0,          # filled in Step 5
                "files":     list({s.get("file_path", "") for s in group_syms}),
                "symbols":   [s.get("symbol_id", "") for s in group_syms],
            }

        project_graph["modules"] = labelled_modules
        logger.info(f"[Step 4] Done — {len(labelled_modules)} modules labelled")
        return StepOutput(
            step_name="generate_module_labelling",
            content=json.dumps({"project_graph": project_graph}, default=str),
            success=True,
        )

    except Exception as e:
        logger.error(f"[Step 4] Failed: {e}")
        return StepOutput(step_name="generate_module_labelling", content=str(e), success=False, error=str(e))


# ── Step 5: Complexity scoring ────────────────────────────────────────────
def generate_complexity(step_input: StepInput) -> StepOutput:
    """
    Step 5 — Computes symbol-wise and module-wise complexity scores.
    Scores relative to the most complex symbol/module, out of 10.
    """
    try:
        step4 = json.loads(step_input.get_step_content("generate_module_labelling") or "{}")
        if step4.get("skipped"):
            return StepOutput(
                step_name="generate_complexity",
                content=json.dumps({"project_graph": step4.get("project_graph", {}), "skipped": True}, default=str),
                success=True,
            )
        project_graph = step4.get("project_graph", {})

        # Step 1: Compute raw AST complexity
        project_graph = compute_ast_complexity(project_graph)

        symbols = project_graph.get("symbols", [])
        modules = project_graph.get("modules", {})

        # ─────────────────────────────────────────────
        # Step 2: Symbol complexity relative out of 10
        # ─────────────────────────────────────────────
        max_c = max((s.get("complexity", 0.0) for s in symbols), default=1.0)

        for s in symbols:
            raw = s.get("complexity", 0.0)
            s["complexity_raw"] = raw
            s["complexity"] = round(min(raw / max_c * 10, 10.0), 2) if max_c > 0 else 0.0

        # ─────────────────────────────────────────────
        # Step 3: Aggregate module complexity (raw)
        # ─────────────────────────────────────────────
        sym_complexity_map = {
            s.get("symbol_id", ""): s.get("complexity_raw", 0.0)
            for s in symbols
        }

        module_raw_scores = {}
        if isinstance(modules, dict):
            for mod_name, mod_data in modules.items():
                module_raw_scores[mod_name] = sum(
                    sym_complexity_map.get(sid, 0.0)
                    for sid in mod_data.get("symbols", [])
                )

        # ─────────────────────────────────────────────
        # Step 4: Module complexity relative out of 10
        # ─────────────────────────────────────────────
        max_m = max(module_raw_scores.values(), default=1.0)

        for mod_name, mod_data in modules.items():
            raw = module_raw_scores.get(mod_name, 0.0)
            mod_data["complexity_raw"] = raw
            mod_data["complexity"] = round(min(raw / max_m * 10, 10.0), 2) if max_m > 0 else 0.0

        project_graph["modules"] = modules

        logger.info("[Step 5] Done — complexity (0–10) applied")

        return StepOutput(
            step_name="generate_complexity",
            content=json.dumps({"project_graph": project_graph}, default=str),
            success=True,
        )

    except Exception as e:
        logger.error(f"[Step 5] Failed: {e}")
        return StepOutput(
            step_name="generate_complexity",
            content=str(e),
            success=False,
            error=str(e),
        )


# ── Step 6: Assemble & persist knowledge graph ────────────────────────────
def generate_knowledge_graph(step_input: StepInput) -> StepOutput:
    """
    Step 6 — Assembles outputs from all previous steps into the final knowledge graph
             and persists it to disk.
    Input  : outputs from Steps 1–5 (via get_step_content)
    Output : success message string; knowledge_graph.json written to disk
    """
    legacy_code_step_id      = AgentEventMessages.LEGACY_CODE_STEP_ID
    legacy_code_step_name    = AgentEventMessages.LEGACY_CODE_STEP_NAME
    legacy_code_msg_group_id = MigrationEvent.LEGACY_CODE_ANALYSIS
    legacy_code_result       = AgentEventMessages.LEGACY_CODE_STEP_RESULT
    user = None
    try:
        user        = current_user.get()
        source_path = step_input.input or ""
        target_path = target_path_ctx.get() or ""
        step1 = json.loads(step_input.get_step_content("generate_project_graph") or "{}")
        if step1.get("skipped"):
            migration_dir        = get_migration_directory("", "")
            knowledge_graph_file = migration_dir / "knowledge_graph.json"
            logger.info("Knowledge graph already exists — skipping reassembly")
            return StepOutput(
                step_name="generate_knowledge_graph",
                content=json.dumps({"knowledge_graph_path": str(knowledge_graph_file)}),
                success=True,
            )
        step3 = json.loads(step_input.get_step_content("generate_tech_data")      or "{}")
        step5 = json.loads(step_input.get_step_content("generate_complexity")     or "{}")

        # Step 5 has the fully enriched project_graph; fall back up the chain if missing
        project_graph = (
            step5.get("project_graph")
            or json.loads(step_input.get_step_content("generate_module_labelling") or "{}").get("project_graph")
            or json.loads(step_input.get_step_content("generate_symbol_roles")     or "{}").get("project_graph")
            or step1.get("project_graph", {})
        )
        tech            = step3.get("tech", {})
        non_convertible = step1.get("non_convertible", [])

        # ── Average complexity from fully scored symbols ───────────────────
        symbols = project_graph.get("symbols", [])
        complexities = [s.get("complexity", 0.0) for s in symbols if s.get("complexity") is not None]
        tech["total_complexity"] = round(sum(complexities) / len(complexities), 2) if complexities else 0.0
        # ── Merge test hierarchy stats into tech_data if present ──────────────
        test_stats = project_graph.get("test_hierarchy_stats")
        if test_stats:
            tech["test_hierarchy_stats"] = test_stats
        
        knowledge_graph = {
            "project_graph":         project_graph,
            "tech_data":             tech,
            "non_convertible_files": non_convertible,
            "file_paths":            _collect_file_paths(Path(source_path)) if source_path else [],
            "Folder_structure":       get_folder_structure(Path(target_path)) if target_path else [],
        }
        _send_migration_summary(knowledge_graph, user)

        # Send table response
        extracted_data = extract_migration_data(knowledge_graph)
        summary_message = generate_full_migration_response(extracted_data)
        _notify_migration_table(summary_message, user)
        migration_dir = get_migration_directory("", "")
        migration_dir.mkdir(parents=True, exist_ok=True)
        knowledge_graph_file = migration_dir / "knowledge_graph.json"
        knowledge_graph_file.write_text(
            json.dumps(knowledge_graph, indent=2, default=str),
            encoding="utf-8",
        )
        logger.info("Saved knowledge_graph.json: %s", knowledge_graph_file)

       
        migration_name = migration_name_ctx.get("")
        if migration_name:
            try:
                user_id = user.id if user else None
                get_json_artifact_repository().save_json_artifact(
                    migration_name, ArtifactType.KNOWLEDGE_GRAPH, knowledge_graph, user_id=user_id
                )
                logger.info("Saved knowledge_graph to DB artifact store")
            except Exception as _exc:
                logger.warning("Failed to save knowledge_graph to DB: %s", _exc)

        # syntactic_count, non_convertible_count, tech_out = _collect_scan_statistics(knowledge_graph)
        # _log_scan_statistics(syntactic_count, non_convertible_count, tech_out)

        # if tech_out.get("language"):
        #     _send_language_event(user, tech_out)
        # if tech_out.get("framework"):
        #     _send_framework_event(user, tech_out)
        # _send_final_scan_metrics(user, syntactic_count, 0, non_convertible_count, tech_out)
        # _send_step_result(
        #     legacy_code_step_id, legacy_code_step_name,
        #     legacy_code_result, user, legacy_code_msg_group_id,
        # )

        return StepOutput(
            step_name="generate_knowledge_graph",
            content=json.dumps({"knowledge_graph_path": str(knowledge_graph_file)}),
            success=True,
        )

    except Exception as e:
        logger.error(f"[Step 6] Failed: {e}")
        if user:
            _send_step_error(
                legacy_code_step_id, legacy_code_step_name,
                AgentEventMessages.ERROR_LEGACY_CODE_ANALYSIS.format(error=str(e)),
                user, legacy_code_msg_group_id,
            )
        return StepOutput(step_name="generate_knowledge_graph", content=str(e), success=False, error=str(e))


TARGET_CODE_ANALYSIS_STEP_ID = AgentEventMessages.TARGET_CODE_ANALYSIS_STEP_ID
TARGET_CODE_ANALYSIS_STEP_NAME = AgentEventMessages.TARGET_CODE_ANALYSIS_STEP_NAME
TARGET_CODE_ANALYSIS_MSG_GROUP_ID = MigrationEvent.TARGET_CODE_ANALYSIS



