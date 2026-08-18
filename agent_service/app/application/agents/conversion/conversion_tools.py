
import os
import re
import json
import shutil
import logging
from pathlib import Path
from agno.tools import tool
from typing import Optional
from agno.workflow.types import StepInput, StepOutput
from app.infrastructure.utils.enums.msg_group import MsgGroup
from app.infrastructure.utils.user_context import current_user
from app.infrastructure.utils.file_utils import read_json_file
from app.infrastructure.utils.file_utils import get_migration_directory
from app.infrastructure.utils.enums.migration_event import MigrationEvent
from app.infrastructure.utils.Constants.agent_event import AgentEventMessages
from app.infrastructure.utils.Agent_helpers.conversion_helper import _extract_clean_code, _send_plan_step_progress
from app.infrastructure.repositories.prompt_repository import fetch_prompt_from_db
import app.application.agents.knowledge_base.knowledge_base_agent as kb
from app.application.agents.conversion.conversion_agent import conversion_agent
from app.infrastructure.utils.Agent_helpers.conversion_helper import _conversion_event_helper
from app.infrastructure.utils.language_adapters import adapter_for_file, get_adapter, ExecutionContract
from app.domain.interfaces.i_folder_structure_goals_repository import (
    IFolderStructureGoalsRepository,
)
from app.domain.interfaces.i_json_artifact_repository import (
    IJsonArtifactRepository,
)
from app.infrastructure.repositories.folder_structure_goals_repository import (
    get_folder_structure_goals_repository,
    SCOPE_SOURCE,
)
from app.infrastructure.repositories.json_artifact_repository import (
    get_json_artifact_repository,
    SCOPE_TARGET,
)
from app.infrastructure.utils.file_utils import _get_runtime_tech_context
from app.infrastructure.utils.migration_context_resolver import resolve_target_path
from app.infrastructure.utils.migration_context_resolver import (
    resolve_description,
    resolve_is_frontend,
    resolve_target_architecture,
    resolve_target_frontend_architecture,
    resolve_target_framework,
    resolve_target_frontend,
    resolve_target_language,
)
from app.infrastructure.utils.Constants.validation_messages import ValidationMessages as VM
from app.infrastructure.utils.migration_context import migration_name_ctx, source_path_ctx, target_language_ctx, target_path_ctx
from app.infrastructure.utils.token_tracker import track_tokens
from app.infrastructure.utils.event_helper import MigrationEventHelper
from app.infrastructure.utils.enums.migration_event import MigrationEvent
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)
_conversion_step_start_sent: set = set()

_folder_goals_repo: Optional[IFolderStructureGoalsRepository] = None
_json_artifact_repo: Optional[IJsonArtifactRepository] = None
__all__=[
    "get_symbol_meta_by_id",
    "get_source_code",
    "get_dependencies",
    "generate_new_code",
    "save_code_to_kb",  
]
def configure_conversion_repositories(
    *,
    folder_goals_repo: Optional[IFolderStructureGoalsRepository] = None,
    json_artifact_repo: Optional[IJsonArtifactRepository] = None,
) -> None:
    """Configure repository dependencies for conversion tools."""
    global _folder_goals_repo, _json_artifact_repo
    if folder_goals_repo is not None:
        _folder_goals_repo = folder_goals_repo
    if json_artifact_repo is not None:
        _json_artifact_repo = json_artifact_repo
def _get_folder_goals_repo() -> IFolderStructureGoalsRepository:
    global _folder_goals_repo
    if _folder_goals_repo is None:
        _folder_goals_repo = get_folder_structure_goals_repository()
    return _folder_goals_repo
def _get_json_artifact_repo() -> IJsonArtifactRepository:
    global _json_artifact_repo
    if _json_artifact_repo is None:
        _json_artifact_repo = get_json_artifact_repository()
    return _json_artifact_repo
def get_symbol_meta_by_id(step_input: StepInput) -> dict:
    """Fetches meta data for a given symbol by filtering KB"""
    input_dict  = step_input.input
    symbol_id   = input_dict.get("symbol_id")
    symbol_hash = input_dict.get("symbol_hash")   # ← prefer hash when available

    symbol_name = input_dict.get("symbol_name") or (
        symbol_id.split("_", 1)[1] if symbol_id and "_" in symbol_id else symbol_id
    )

    try:
        user = current_user.get()
        _conversion_event_helper.send_step_log(
            AgentEventMessages.MIGRATION_PROGRESS_STEP_ID,
            f"Fetching metadata for: {symbol_id}",
            user,
            MigrationEvent.MIGRATION_PROGRESS,
        )
    except Exception:
        pass

    symbol_docs = kb.source_knowledge.search(
        query=symbol_name,   # ← use actual symbol name
        filters={
            # "symbol_id": symbol_id,
            "symbol_hash": symbol_hash,
            "doc_type":  "source_symbol",
        },
        search_type="hybrid"
        # max_results=1
    )
    output = {
        "content": symbol_docs[0].content,
        "meta_data": symbol_docs[0].meta_data
    }
    _send_plan_step_progress(1, input_dict.get("plan_id", ""))
    return StepOutput(content=output)

def read_lines(file_path, start, end):
    with open(file_path, 'r', encoding="utf-8") as f:
        lines = f.readlines()
    # Adjust for 1-based index (assuming these are 1-based, inclusive)
    selected_lines = lines[start-1:end]
    raw_code = ''.join(selected_lines)
    return raw_code

def get_source_code(step_input: StepInput) -> str:
    """Reads and returns lines of code from file_path between start and end (inclusive, 1-based)."""
    input_dict = step_input.get_step_content("get_symbol_meta_by_id")
    meta_data = input_dict.get("meta_data")
    file_path = meta_data.get("file_path")
    symbol_id = meta_data.get("symbol_id")
    symbol_hash = meta_data.get("symbol_hash")
    # Split plans carry a specific source_line_range per part in workflow_input
    # 1:1 plans fall back to the full symbol line_range from KB
    workflow_input = step_input.input
    source_line_range = workflow_input.get("source_line_range")
    if source_line_range:
        start = int(source_line_range.get("start", 0))
        end   = int(source_line_range.get("end", 0))
    else:
        line_range = meta_data.get("line_range", {})
        start = int(line_range.get("start", 0))
        end   = int(line_range.get("end", 0))
    print("---", file_path, symbol_id, start, end)

    try:
        user = current_user.get()
        _conversion_event_helper.send_step_log(
            AgentEventMessages.MIGRATION_PROGRESS_STEP_ID,
            f"Reading source code for {symbol_id} (lines {start}–{end})",
            user,
            MigrationEvent.MIGRATION_PROGRESS,
        )
    except Exception:
        pass

    try:
        raw_code = read_lines(file_path, start, end)
        output = {
            "file_path":  file_path,
            "line_range": {"start": start, "end": end},
            "symbol_id":  symbol_id,
            "symbol_hash": symbol_hash,
            "raw_code":   raw_code,
        }
        _send_plan_step_progress(2, workflow_input.get("plan_id", ""))
        return StepOutput(content=output)
    except Exception as e:
        return StepOutput(content={"error": str(e)})
def get_dependencies(step_input: StepInput) -> StepOutput:
    """Fetches dependent converted snippets and file-level import dependencies."""
    workflow_input     = step_input.input
    print(workflow_input, "@@@@@@@@@@@@@@@@@@")
    target_file_path   = workflow_input.get("target_file")
    target_symbol_name = workflow_input.get("target_symbol_name")
    source_file_path   = workflow_input.get("file_path")
    depends_on_plans   = workflow_input.get("depends_on_plans") or []
    # ── Dependent converted snippets ──────────────────────────────────────
    dependencies = []
    for plan_id in depends_on_plans:
        print(plan_id, "======")
        converted_docs = kb.target_knowledge.search(
            query="*",
            filters={
                "plan_id":  plan_id,
                "doc_type": "migrated_code",
            },
            search_type="hybrid",
        )
        if converted_docs:
            dependencies.append(converted_docs[0].content)

   # ── Fetch planned libraries from KB for code generation context ───────
    planned_dep_docs = kb.target_knowledge.search(
        query="*",
        filters={"doc_type": "target_dependency"},
        search_type="hybrid",
        max_results=200,
    )
    planned_libraries = sorted({
        doc.meta_data.get("package_name")
        for doc in planned_dep_docs
        if doc.meta_data.get("package_name")
    })
    planned_libs_content = "\n".join(planned_libraries) if planned_libraries else "None"
    # ─────────────────────────────────────────────────────────────────────

    try:
        user = current_user.get()
        _conversion_event_helper.send_step_log(
            AgentEventMessages.MIGRATION_PROGRESS_STEP_ID,
            f"Resolved {len(dependencies)} converted deps and {len(planned_libs_content)} import deps for {Path(target_file_path).name}",
            user,
            MigrationEvent.MIGRATION_PROGRESS,
        )
    except Exception:
        pass
    _send_plan_step_progress(3, workflow_input.get("plan_id", ""))
    return StepOutput(content={
        "target_file_path":        target_file_path,
        "target_symbol_name":      target_symbol_name,
        "dependent_code_snippets": dependencies,
        "file_dependencies":       planned_libs_content,
    })

def generate_new_code(step_input: StepInput) -> dict:
    """Fetches meta data for a given symbol by filtering KB"""
    # print(step_input, "+++")
    prev_output = step_input.get_step_content("get_source_code")
    source_code = prev_output.get("raw_code") 
    source_file_path = prev_output.get("file_path")
    symbol_id = prev_output.get("symbol_id")
    symbol_hash = prev_output.get("symbol_hash")
    workflow_input = step_input.input
    target_file_path = workflow_input.get("target_file")
    target_symbol_name = workflow_input.get("target_symbol_name")
    runtime_tech = _get_runtime_tech_context()
    dependencies_output =  step_input.get_step_content("get_dependencies")
    file_deps = dependencies_output.get("file_dependencies")
    deps = dependencies_output.get("dependent_code_snippets")
    file_deps_content = file_deps if isinstance(file_deps, str) else "\n".join(file_deps)
    deps_content = "\n".join(deps)
    tech_summary = (
        f"Target Language : {runtime_tech['language']}\n"
        f"Framework       : {runtime_tech['framework'] or 'None'}\n"
        f"Architecture    : {runtime_tech['architecture'] or 'Unknown'}\n"
    )

    # Resolve executable behavior through the language adapter registry. The
    # conversion engine never branches on source/target language itself.
    execution_contract = None
    entrypoint_context = ""
    try:
        source_adapter = adapter_for_file(Path(str(source_file_path)))
        if source_adapter is not None:
            execution_contract = source_adapter.detect_execution_contract(
                Path(str(source_file_path)), target_symbol_name
            )
        if execution_contract and execution_contract.executable:
            target_adapter = get_adapter(runtime_tech.get("language", ""))
            target_name = target_adapter.display_name if target_adapter else runtime_tech.get("language", "target")
            entrypoint_context = (
                "SOURCE EXECUTION CONTRACT: the source module executes the translated "
                f"symbol '{execution_contract.entry_symbol}'. Preserve that runtime behavior "
                f"using the idiomatic executable entry-point convention of the target language ({target_name}). "
                "Do not add an entry point when the source is clearly a reusable library/module."
            )
    except Exception:
        execution_contract = None
        entrypoint_context = ""

    try:
        user = current_user.get()
        migration_name = migration_name_ctx.get(None)
        if migration_name not in _conversion_step_start_sent:
            _conversion_step_start_sent.add(migration_name)
            _conversion_event_helper.send_step_start(
                AgentEventMessages.MIGRATION_PROGRESS_STEP_ID,
                AgentEventMessages.MIGRATION_PROGRESS_STEP_NAME,
                user,
                MigrationEvent.MIGRATION_PROGRESS,
            )
            _conversion_event_helper.send_step_description(
                AgentEventMessages.MIGRATION_PROGRESS_STEP_ID,
                AgentEventMessages.MIGRATION_PROGRESS_STEP_NAME,
                user,
                MigrationEvent.MIGRATION_PROGRESS,
            )
        _conversion_event_helper.send_step_log(
            AgentEventMessages.MIGRATION_PROGRESS_STEP_ID,
            f"Generating converted code for: {target_symbol_name} → {target_file_path}",
            user,
            MigrationEvent.MIGRATION_PROGRESS,
        )
    except Exception:
        pass

    resp = conversion_agent.run(input=f"""
        Convert the given source symbol into equivalent target language code while making
        sure any dependencies are resolved/imported correctly and any similar 
        code snippets (if given) are used as coding/formatting guidelines.
        SOURCE CODE: {source_code}
        SYMBOL ID : {symbol_id}
        SYMBOL HASH : {symbol_hash}
        SOURCE SYMBOL FILE PATH : {source_file_path}
        TARGET TECH SUMMARY: {tech_summary}
        EXISTING DEPENDENCIES TO USE: {deps_content} 
        EXISTING SIMILAR CODE SNIPPETS: []
        PRE-APPROVED LIBRARIES (from dependency file — use these for imports, do not invent others): {file_deps_content}
        {entrypoint_context}
        When writing the target code, make sure to correctly use the exisisting dependencies alongwith their correct import paths/naming conventions.
        Return just the final raw code, no extra explanations & no extra formatting such as ```python, ```, etc.  
        """
        )

    target_code = _extract_clean_code((resp.content or "").strip())
    if target_code.startswith("```"):
        target_code = target_code.split("\n", 1)[1] if "\n" in target_code else ""
    if target_code.endswith("```"):
        target_code = target_code.rsplit("\n", 1)[0] if "\n" in target_code else target_code[:-3]

    target_adapter = get_adapter(runtime_tech.get("language", ""))
    if target_adapter is not None and execution_contract is not None:
        target_code = target_adapter.ensure_entrypoint(
            target_code, execution_contract, target_symbol_name
        )

    track_tokens(resp, source="conversion:symbol_convert")

    try:
        user = current_user.get()
        _conversion_event_helper.send_step_result(
            AgentEventMessages.MIGRATION_PROGRESS_STEP_ID,
            AgentEventMessages.MIGRATION_PROGRESS_STEP_NAME,
            f"Code generated for {target_symbol_name}",
            user,
            MigrationEvent.MIGRATION_PROGRESS,
        )
    except Exception:
        pass
    _send_plan_step_progress(4, workflow_input.get("plan_id", ""))
    return StepOutput(content={
        "target_code": target_code,
        "symbol_hash": symbol_hash, 
    })

def save_code_to_kb(step_input: StepInput) -> StepOutput:
    """Save converted code to file and KB, track part-wise completion."""
    workflow_input     = step_input.input
    target_file_path   = workflow_input.get("target_file")
    target_symbol_name = workflow_input.get("target_symbol_name")
    source_file_path   = workflow_input.get("file_path")
    source_symbol_id   = workflow_input.get("symbol_id")
    source_symbol_name = workflow_input.get("symbol_name")
    plan_id            = workflow_input.get("plan_id")
    total_parts        = workflow_input.get("total_parts")
    prev_output  = step_input.get_step_content("generate_new_code")
    target_code  = prev_output.get("target_code") or ""
    source_symbol_hash = prev_output.get("symbol_hash")
    # ── Write file to migration output directory ───────────────────────────
    migration_dir = get_migration_directory("", "")
    output_path   = migration_dir / "Migrated Code" / target_file_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists():
        existing_lines = sum(1 for _ in output_path.open("r", encoding="utf-8"))
    else:
        existing_lines = 0
    new_lines  = target_code.count("\n") + 1 if target_code else 0
    start_line = existing_lines + 1
    end_line   = existing_lines + new_lines
    with output_path.open("a", encoding="utf-8") as f:
        if output_path.stat().st_size > 0:
            f.write("\n\n")
            start_line += 2
            end_line   += 2
        f.write(target_code)

    try:
        user = current_user.get()
        _conversion_event_helper.send_step_log(
            AgentEventMessages.MIGRATION_PROGRESS_STEP_ID,
            f"Saved {target_symbol_name} to {str(output_path)} (lines {start_line}–{end_line})",
            user,
            MigrationEvent.MIGRATION_PROGRESS,
        )
    except Exception:
        pass

    # ── Store converted part in target KB ─────────────────────────────────
    meta_data = {
        "source_symbol_id":   source_symbol_id,
        "source_symbol_hash": source_symbol_hash,
        "source_file_path":   source_file_path,
        "source_symbol_name": source_symbol_name,
        "target_symbol_name": target_symbol_name,
        "target_file_path":   target_file_path,
        "doc_type":           "migrated_code",
        "origin":             "converted",
        "line_range":         {"start": start_line, "end": end_line},
        "plan_id":            plan_id,
        "status":             "completed",
    }
    document = {
        "name":         f"{target_symbol_name}_{plan_id}",
        "text_content": target_code,
        "metadata":     meta_data,
    }
    kb.target_knowledge.insert(**document)

    try:
        user = current_user.get()
        _conversion_event_helper.send_step_log(
            AgentEventMessages.MIGRATION_PROGRESS_STEP_ID,
            f"Stored {target_symbol_name} in target knowledge base",
            user,
            MigrationEvent.MIGRATION_PROGRESS,
        )
    except Exception:
        pass

    # ── Part-wise completion check ─────────────────────────────────────────
    is_split = "_part_" in plan_id
    if is_split:
        base_plan = plan_id.rsplit("_part_", 1)[0]

        all_converted = kb.target_knowledge.search(
            query="*",
            filters={
                # "source_symbol_id": source_symbol_id,
                "source_symbol_hash": source_symbol_hash,
                "doc_type":         "migrated_code",
            },
            search_type="hybrid",
        )
        completed_part_ids = {
            doc.meta_data.get("plan_id")
            for doc in all_converted
            if doc.meta_data.get("status") == "completed"
            and doc.meta_data.get("plan_id", "").startswith(base_plan + "_part_")
        }
        if not total_parts:
            total_parts = sum(
                1 for doc in all_converted
                if doc.meta_data.get("plan_id", "").startswith(base_plan + "_part_")
            )
            logger.warning(
                f"total_parts not in workflow input for {plan_id}, "
                f"inferred {total_parts} from KB"
            )
        total_parts    = int(total_parts)
        all_parts_done = len(completed_part_ids) >= total_parts
        logger.info(
            f"Split plan progress — symbol: {source_symbol_id}, "
            f"base: {base_plan}, "
            f"completed: {len(completed_part_ids)}/{total_parts}, "
            f"all_done: {all_parts_done}"
        )
    else:
        all_parts_done = True
        total_parts    = 1
        logger.info(f"1:1 plan completed — symbol: {source_symbol_id}")
    # ── Mark symbol completed in source KB when all parts done ────────────
    if all_parts_done:
        try:
            user = current_user.get()
            parts_label = f"all {total_parts} parts" if is_split else "1:1"
            _conversion_event_helper.send_step_result(
                AgentEventMessages.MIGRATION_PROGRESS_STEP_ID,
                AgentEventMessages.MIGRATION_PROGRESS_STEP_NAME,
                f"Symbol '{source_symbol_name}' fully converted ({parts_label})",
                user,
                MigrationEvent.MIGRATION_PROGRESS,
            )
        except Exception:
            pass
        existing_docs = kb.source_knowledge.search(
            query="*",
            filters={
                # "symbol_id": source_symbol_id,
                "symbol_hash": source_symbol_hash,
                "doc_type":  "source_symbol",
            },
        )
        
        if existing_docs:
            doc              = existing_docs[0]
            updated_metadata = doc.meta_data.copy()
            updated_metadata["migration_status"] = "completed"
            kb.source_knowledge.insert(
                name=doc.name,
                text_content=doc.content,
                metadata=updated_metadata,
            )
            logger.info(
                f"✅ Symbol COMPLETED: {source_symbol_id} "
                f"({'all ' + str(total_parts) + ' parts done' if is_split else '1:1'})"
            )
        else:
            # If an exact KB hash filter misses after re-indexing, fall back to
            # the authoritative source knowledge graph so completion state is
            # not lost merely because vector metadata changed.
            try:
                graph_path = migration_dir / "knowledge_graph.json"
                graph = json.loads(graph_path.read_text(encoding="utf-8")) if graph_path.exists() else {}
                source_symbols = graph.get("project_graph", {}).get("symbols", [])
                source_sym = next((s for s in source_symbols if isinstance(s, dict) and s.get("symbol_id") == source_symbol_id), None)
                if source_sym:
                    canonical_meta = {
                        "symbol_id": source_sym.get("symbol_id", source_symbol_id),
                        "symbol_type": source_sym.get("symbol_type", ""),
                        "symbol_name": source_sym.get("name", source_symbol_name),
                        "symbol_hash": source_sym.get("symbol_hash", source_symbol_hash),
                        "parent_symbol": source_sym.get("parent_symbol", ""),
                        "module": source_sym.get("module", ""),
                        "language": source_sym.get("language", ""),
                        "access": source_sym.get("access", ""),
                        "inherits": source_sym.get("inherits", []),
                        "line_range": source_sym.get("line_range", ""),
                        "file_path": source_sym.get("file_path", source_file_path),
                        "calls": source_sym.get("calls", []),
                        "dependencies": source_sym.get("dependencies", []),
                        "parameters": source_sym.get("parameters", []),
                        "return_type": source_sym.get("return_type", ""),
                        "summary": source_sym.get("summary", ""),
                        "meta": source_sym.get("meta", {}),
                        "role": source_sym.get("role", ""),
                        "complexity": source_sym.get("complexity"),
                        "doc_type": "source_symbol",
                        "origin": "existing",
                        "migration_status": "completed",
                    }
                    content = (
                        f"Symbol ID: {canonical_meta['symbol_id']}\n"
                        f"Symbol Name: {canonical_meta['symbol_name']}\n"
                        f"Symbol Summary: {canonical_meta['summary']}\n"
                        f"Symbol Role: {canonical_meta['role']}"
                    )
                    kb.source_knowledge.insert(name=canonical_meta["symbol_id"], text_content=content, metadata=canonical_meta)
                    logger.info("✅ Symbol COMPLETED: %s (rehydrated from knowledge_graph.json)", source_symbol_id)
                else:
                    logger.warning("Symbol %s not found in source KB or knowledge graph — completion state cannot be persisted", source_symbol_id)
            except Exception:
                logger.exception("Failed to rehydrate source KB completion state for %s", source_symbol_id)
    _send_plan_step_progress(5, workflow_input.get("plan_id", ""))
    return StepOutput(content={
        "document":   document,
        "written_to": str(output_path),
    })
