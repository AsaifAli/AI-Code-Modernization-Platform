import os
import re
import json
import logging
import ast as _ast
from pathlib import Path
from agno.tools import tool
from textwrap import dedent
from typing import Optional, Any
from dotenv import load_dotenv
from agno.workflow.types import StepInput, StepOutput
from statistics import mean as _mean, stdev as _stdev, median as _median
import app.application.agents.knowledge_base.knowledge_base_agent as kb
from app.application.agents.utility_agent import utility_agent
from app.domain.interfaces.i_file_mapping_repository import IFileMappingRepository
from app.domain.interfaces.i_folder_structure_goals_repository import (
    IFolderStructureGoalsRepository,
)
from app.domain.interfaces.i_json_artifact_repository import IJsonArtifactRepository
from app.domain.interfaces.i_migration_scan_result_repository import (
    IMigrationScanResultRepository,
)
from app.application.agents.planning.planning_agent import dependency_agent
from app.infrastructure.utils.Agent_helpers.planning_helper import _extract_json
from app.infrastructure.utils.user_context import current_user
from app.infrastructure.utils.Constants.app_constants import AgentConstants
from app.infrastructure.utils.Constants.migration import MigrationConstants
from app.infrastructure.utils.Constants.app_constants import MigrationScope, ArtifactType
from app.infrastructure.repositories.migration_scan_result_repository import get_migration_scan_result_repository
from app.infrastructure.repositories.json_artifact_repository import (
    get_json_artifact_repository,
    SCOPE_SOURCE,
    SCOPE_TARGET,
)
from app.infrastructure.repositories.file_mapping_repository import (
    get_file_mapping_repository,
)
from app.infrastructure.repositories.folder_structure_goals_repository import (
    get_folder_structure_goals_repository,
)
from app.infrastructure.utils.enums.migration_event import MigrationEvent
from app.infrastructure.agents_backend.model_provider import model_embedder
from app.infrastructure.utils.Constants.agent_event import AgentEventMessages
from app.infrastructure.utils.Agent_helpers.planning_helper import *
from app.infrastructure.utils.token_tracker import track_tokens
from app.infrastructure.utils.file_utils import _get_runtime_tech_context
from app.infrastructure.utils.dependency_artifact_utils import extract_dependency_packages
from app.infrastructure.repositories.prompt_repository import fetch_prompt_from_db
from app.infrastructure.utils.Constants.validation_messages import ValidationMessages as VM
from app.infrastructure.utils.file_utils import get_migration_directory, read_json_file, parse_json_response
from app.infrastructure.utils.migration_context import migration_name_ctx,source_path_ctx,target_language_ctx,target_path_ctx
from app.infrastructure.utils.migration_context_resolver import (
    resolve_description,
    resolve_target_architecture,
    resolve_target_frontend_architecture,
    resolve_target_framework,
    resolve_is_frontend,
    resolve_target_frontend,
    resolve_target_language,
)
load_dotenv()
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)
MODEL_TYPE = os.getenv("MODEL_TYPE", "OpenAI")
PLANNING_LLM_TIMEOUT_SEC = int(os.getenv("PLANNING_LLM_TIMEOUT_SEC", "180"))

_file_mapping_repo: Optional[IFileMappingRepository] = None
_folder_goals_repo: Optional[IFolderStructureGoalsRepository] = None
_json_artifact_repo: Optional[IJsonArtifactRepository] = None
_migration_scan_repo: Optional[IMigrationScanResultRepository] = None

__all__ = [
    "get_symbol_module_meta",
    "generate_symbols_transformation",
    "generate_migration_plan",
    "generate_dependency_plan",
]

def configure_planning_repositories(
    *,
    file_mapping_repo: Optional[IFileMappingRepository] = None,
    folder_goals_repo: Optional[IFolderStructureGoalsRepository] = None,
    json_artifact_repo: Optional[IJsonArtifactRepository] = None,
    migration_scan_repo: Optional[IMigrationScanResultRepository] = None,
) -> None:
    """Configure repository dependencies for planning tools (for DI/testing)."""
    global _file_mapping_repo, _folder_goals_repo, _json_artifact_repo, _migration_scan_repo
    if file_mapping_repo is not None:
        _file_mapping_repo = file_mapping_repo
    if folder_goals_repo is not None:
        _folder_goals_repo = folder_goals_repo
    if json_artifact_repo is not None:
        _json_artifact_repo = json_artifact_repo
    if migration_scan_repo is not None:
        _migration_scan_repo = migration_scan_repo


def _coerce_step_payload(value: Any) -> dict:
    """Normalize Agno step content across dict/JSON/StepOutput representations."""
    if value is None:
        return {}
    if isinstance(value, StepOutput):
        value = getattr(value, "content", None)
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return {}
        for parser in (json.loads, _ast.literal_eval):
            try:
                parsed = parser(text)
                if isinstance(parsed, StepOutput):
                    parsed = getattr(parsed, "content", None)
                if isinstance(parsed, dict):
                    return parsed
            except Exception:
                continue
    return {}


def _fallback_symbol_module_meta() -> dict:
    """Recover planning inputs directly from the source KB when workflow step state is unavailable."""
    symbol_docs = kb.source_knowledge.search(
        query="*",
        filters={
            MigrationConstants.DOC_TYPE: MigrationConstants.DOC_TYPE_SOURCE_SYMBOL,
            MigrationConstants.MIGRATION_STATUS: MigrationConstants.STATUS_PENDING,
        },
        max_results=1000,
    )
    module_docs = kb.source_knowledge.search(query="*", filters={"doc_type": "module"}, max_results=1000)
    path_docs = kb.source_knowledge.search(query="*", filters={"doc_type": "file_path"}, max_results=1000)
    threshold_docs = kb.source_knowledge.search(query="*", filters={"doc_type": "test_hierarchy_thresholds"}, max_results=1)

    symbols = [{
        "symbol_id": d.meta_data.get("symbol_id"),
        "symbol_name": d.meta_data.get("symbol_name"),
        "symbol_type": d.meta_data.get("symbol_type"),
        "symbol_hash": d.meta_data.get("symbol_hash"),
        "file_path": d.meta_data.get("file_path"),
        "meta_data": d.meta_data,
        "content": d.content,
    } for d in symbol_docs if d.meta_data.get("symbol_id")]

    modules = [{
        "module_name": d.meta_data.get("module_name"),
        "summary": d.meta_data.get("summary", ""),
        "symbols": d.meta_data.get("symbols", []),
        "target_folder": d.meta_data.get("target_folder", ""),
        "meta_data": d.meta_data,
        "content": d.content,
    } for d in module_docs]

    paths = [{
        "name": d.meta_data.get("file_path", ""),
        "meta_data": d.meta_data,
        "content": d.content,
    } for d in path_docs]

    thresholds = {}
    if threshold_docs:
        m = threshold_docs[0].meta_data
        thresholds = {
            "group_threshold": int(m.get("group_threshold", 4)),
            "test_threshold": int(m.get("test_threshold", 8)),
            "test_batch_size": int(m.get("test_batch_size", 4)),
        }
    logger.warning("Planning step state did not contain symbols; recovered %d symbols from KB", len(symbols))
    return {"symbols_data": {"symbols": symbols}, "modules_data": {"modules": modules}, "file_path": {"path": paths}, "hierarchy_thresholds": thresholds}


def _get_file_mapping_repo() -> IFileMappingRepository:
    global _file_mapping_repo
    if _file_mapping_repo is None:
        _file_mapping_repo = get_file_mapping_repository()
    return _file_mapping_repo


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


def _get_migration_scan_repo() -> IMigrationScanResultRepository:
    global _migration_scan_repo
    if _migration_scan_repo is None:
        _migration_scan_repo = get_migration_scan_result_repository()
    return _migration_scan_repo


migration_plan_step_id = AgentEventMessages.MIGRATION_PLAN_STEP_ID
migration_plan_step_name = AgentEventMessages.MIGRATION_PLAN_STEP_NAME
migration_plan_msg_group_id = MigrationEvent.MIGRATION_PLAN


def get_symbol_module_meta(step_input: StepInput) -> StepOutput:
    """Fetch all symbols and modules from Knowledge Base"""
     # ── Skip if plan already exists ───────────────────────────────────────
    existing = _load_existing_plan()
    if existing:
        total = sum(len(v.get("plans", [])) for v in existing.values())
        logger.info(f"Plan already exists — {len(existing)} modules, {total} entries. Skipping all planning steps.")
        try:
            user = current_user.get()
            _send_planning_step_log(
                migration_plan_step_id,
                f"Migration plan already exists — {len(existing)} modules, {total} entries. Skipping regeneration.",
                user,
                migration_plan_msg_group_id,
            )
        except Exception:
            pass
        return StepOutput(content={"skipped": True, "module_plans": existing})
    # ─────────────────────────────────────────────────────────────────────

    print("📥 Fetching all symbols and modules from Knowledge Base...")

    symbol_docs = kb.source_knowledge.search(
        query="*",
        filters={
            MigrationConstants.DOC_TYPE: MigrationConstants.DOC_TYPE_SOURCE_SYMBOL,
            MigrationConstants.MIGRATION_STATUS: MigrationConstants.STATUS_PENDING,
        },
        max_results=1000
    )

    module_docs = kb.source_knowledge.search(
        query="*",
        filters={"doc_type": "module"},
        max_results=1000
    )

    path_docs = kb.source_knowledge.search(
        query="*",
        filters={"doc_type": "file_path"},
        max_results=1000
    )
    
    threshold_docs = kb.source_knowledge.search(
    query="*",
    filters={"doc_type":"test_hierarchy_thresholds"},
    max_results=1
    )


    symbols = []
    for doc in symbol_docs:
        symbols.append({
            "symbol_id": doc.meta_data.get("symbol_id"),
            "symbol_name": doc.meta_data.get("symbol_name"),
            "symbol_type": doc.meta_data.get("symbol_type"),
            "symbol_hash": doc.meta_data.get("symbol_hash"),
            "file_path": doc.meta_data.get("file_path"),
            "meta_data": doc.meta_data,
            "content": doc.content
        })

    modules = []
    for doc in module_docs:
        modules.append({
            "module_name": doc.meta_data.get("module_name"),
            "summary": doc.meta_data.get("summary", ""),
            "symbols": doc.meta_data.get("symbols", []),
            "target_folder": doc.meta_data.get("target_folder", ""),
            "meta_data": doc.meta_data,
            "content": doc.content
        })

    path = []
    for doc in path_docs:
        path.append({
            "name":      doc.meta_data.get("file_path", ""),  
            "meta_data": doc.meta_data,
            "content":   doc.content,
        })

    thresholds = {}

    if threshold_docs:

        meta = threshold_docs[0].meta_data

        thresholds = {
            "group_threshold":
                int(meta.get("group_threshold",4)),

            "test_threshold":
                int(meta.get("test_threshold",8)),

            "test_batch_size":
                int(meta.get("test_batch_size",4)),
        }

        logger.info(
            f"Using KB thresholds {thresholds}"
        )

    print(f"✅ Retrieved {len(symbols)} symbols, {len(modules)} modules and {len(path)} file paths")

    try:
        user = current_user.get()
        _send_planning_step_start(migration_plan_step_id, migration_plan_step_name, user, migration_plan_msg_group_id)
        _send_planning_step_description(migration_plan_step_id, migration_plan_step_name, user, migration_plan_msg_group_id)
        _send_planning_step_log(
            migration_plan_step_id,
            f"Fetched {len(symbols)} symbols, {len(modules)} modules and {len(path)} file paths from knowledge base",
            user,
            migration_plan_msg_group_id,
        )
    except Exception:
        pass

    return StepOutput(
    content={
        "symbols_data":{"symbols":symbols},
        "modules_data":{"modules":modules},
        "file_path":{"path":path},
        "hierarchy_thresholds":thresholds
    }
)

def generate_dependency_plan(step_input: StepInput) -> StepOutput:
    """
    Reads source symbols and dependencies from step output (get_symbol_module_meta),
    calls dependency_agent to predict the target dependency file,
    deduplicates, stores in KB, writes file, and returns plan metadata.
    """
    logger.info("📦 Generating dependency plan from source KB...")

    # ── Reuse get_symbol_module_meta output — no re-query needed ──────────
    meta_raw = _coerce_step_payload(step_input.get_step_content("get_symbol_module_meta"))
    if not meta_raw.get("symbols_data", {}).get("symbols"):
        meta_raw = _fallback_symbol_module_meta()
    if meta_raw.get("skipped"):
        return StepOutput(content={"skipped": True})

    symbol_list = (meta_raw.get("symbols_data") or {}).get("symbols", [])

    # ── Collect third-party imports from get_symbol_module_meta step ──────
    # No re-query needed — dep info is already in step content
    dep_docs = kb.source_knowledge.search(
        query="*",
        filters={"doc_type": "source_dependencies"},
        max_results=1000,
        search_type="hybrid",
    )
    all_third_party: list[str] = sorted({
        doc.meta_data.get("name", "")
        for doc in dep_docs
        if doc.meta_data.get("type") == "third_party"
        and doc.meta_data.get("name")
    })

    # ── Build source snippets from symbol content (already chunked in KB) ─
    # Chunking already handles size; use full content from step output
    seen_files: set[str] = set()
    snippets: list[str] = []
    for sym in symbol_list:
        meta = sym.get("meta_data", sym)
        fp   = meta.get("file_path") or sym.get("file_path", "")
        if fp and fp not in seen_files:
            seen_files.add(fp)
            src = sym.get("content", "")
            if src:
                snippets.append(f"# FILE: {Path(fp).name}\n{src}")

    runtime_tech = _get_runtime_tech_context()
    tech_summary = (
        f"Target Language : {runtime_tech['language']}\n"
        f"Framework       : {runtime_tech['framework'] or 'None'}\n"
        f"Architecture    : {runtime_tech['architecture'] or 'Unknown'}\n"
    )

    prompt = f"""
Predict the target dependency file for this migration.

TECH CONTEXT:
{tech_summary}

SOURCE CODE SNIPPETS:
{chr(10).join(snippets)}

DECLARED THIRD-PARTY IMPORTS IN SOURCE:
{json.dumps(sorted(set(all_third_party)), indent=2)}

Rules:
- Output ONLY a JSON object with exactly filename and content.
- Never invent optional libraries just because the target framework commonly uses them.
- Include the target framework runtime package only when the requested target framework requires it.
- For package.json, every dependency value MUST be valid npm syntax such as "latest" or a valid semver range; NEVER use "^" by itself.
- Keep the dependency set minimal.
"""

    resp = dependency_agent.run(input=prompt)
    track_tokens(resp, source="planning:dependency_prediction")

    raw = (resp.content or "").strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1] if "\n" in raw else ""
    if raw.endswith("```"):
        raw = raw.rsplit("\n", 1)[0]

    parsed = _extract_json(raw.strip())
    if parsed and isinstance(parsed, dict):
        filename = parsed.get("filename", "requirements.txt")
        content  = parsed.get("content", "")
    else:
        logger.warning("generate_dependency_plan: JSON extraction failed — empty dependency file")
        filename = "requirements.txt"
        content  = ""

    # Validate/repair structured dependency files before persisting them.
    if filename == "package.json":
        try:
            pkg = json.loads(content) if isinstance(content, str) else {}
            if not isinstance(pkg, dict):
                raise ValueError("package.json must be an object")
            for section in ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies"):
                deps = pkg.get(section)
                if isinstance(deps, dict):
                    cleaned = {}
                    for name, version in deps.items():
                        v = str(version or "latest").strip()
                        if v in {"^", "~", "*", ""}:
                            v = "latest"
                        cleaned[str(name).strip()] = v
                    pkg[section] = cleaned
            # A requested Express target needs its runtime dependency, but do not add
            # unrelated middleware merely because it is common in Express projects.
            if str(runtime_tech.get("framework") or "").lower() == "express":
                pkg.setdefault("dependencies", {})
                pkg["dependencies"].setdefault("express", "latest")
            content = json.dumps(pkg, indent=2) + "\n"
        except Exception as exc:
            logger.warning("Invalid package.json predicted by dependency agent: %s; rebuilding minimal manifest", exc)
            deps = {"express": "latest"} if str(runtime_tech.get("framework") or "").lower() == "express" else {}
            content = json.dumps({"name": "migrated-app", "version": "1.0.0", "private": True, "main": "index.js", "dependencies": deps}, indent=2) + "\n"

    # ── Extract actual packages from the validated dependency artifact. ─────
    # Never split structured JSON line-by-line. This prevents entries such as
    # "{", "dependencies": {, and "}" from becoming fake packages.
    unique_packages: list[str] = extract_dependency_packages(filename, content)

    if unique_packages:
        if filename.endswith(".txt"):
            # Preserve version constraints for plain-text dependency files only
            content_lines = [line.strip() for line in str(content).splitlines() if line.strip() and not line.strip().startswith("#")]
            content = "\n".join(content_lines) + "\n"
        else:
            logger.info("Structured dependency file (%s) contains packages: %s", filename, unique_packages)
    else:
        # An empty dependency set is valid for projects with only stdlib imports.
        # Do not manufacture packages.
        logger.info("No third-party packages detected for %s", filename)

    logger.info(
        "Collected %d declared third-party imports; planned %d unique packages: %s",
        len(all_third_party),
        len(unique_packages),
        unique_packages,
    )

    # ── Store each unique package as target_dependency FIRST ──────────────
    # Store before writing file so KB is source of truth
    if unique_packages:
        kb.target_knowledge.insert_many([
            {
                "name":         f"target_dep_planned_{lib}",
                "text_content": f"Library: {lib}",
                "metadata": {
                    "doc_type":     "target_dependency",
                    "package_name": lib,
                    "origin":       "planned",
                },
            }
            for lib in unique_packages
        ])
        logger.info(f"Stored {len(unique_packages)} planned target dependencies in KB")

    # ── Store dependency file doc in target KB ────────────────────────────
    kb.target_knowledge.insert(
        name="dependency_file",
        text_content=content,
        metadata={
            "doc_type":  "dependency_file",
            "filename":  filename,
            "libraries": unique_packages,
        },
    )

    # ── Write file LAST — after KB is updated ─────────────────────────────
    migration_dir = get_migration_directory()
    output_path   = Path(migration_dir) / "Migrated Code" / filename
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")
    logger.info(f"✅ Dependency file written: {output_path} — {len(unique_packages)} packages")

    try:
        user = current_user.get()
        _send_planning_step_log(
            migration_plan_step_id,
            f"Dependency file predicted: {filename} with {len(unique_packages)} packages: {unique_packages}",
            user,
            migration_plan_msg_group_id,
        )
    except Exception:
        pass

    return StepOutput(content={
        "filename":   filename,
        "packages":   unique_packages,
        "written_to": str(output_path),
    })

def generate_symbols_transformation(step_input: StepInput) -> StepOutput:
    """
    Step 2: one planning_agent call per module produces transformations + naming together.

    Produces: {"transformations": {...}, "naming": [...]}
    """
    
    fetch_content = _coerce_step_payload(step_input.get_step_content("get_symbol_module_meta"))
    if not fetch_content.get("symbols_data", {}).get("symbols"):
        fetch_content = _fallback_symbol_module_meta()

    if fetch_content.get("skipped"):     # ← now safe, always a dict
        return StepOutput(content={"skipped": True})

    symbols_data_raw = fetch_content.get("symbols_data", {})
    modules_data_raw = fetch_content.get("modules_data", {})
    file_path_raw = fetch_content.get("file_path", {})

    # ── Normalise symbol list ─────────────────────────────────────────────────
    if isinstance(symbols_data_raw, dict):
        symbol_list = symbols_data_raw.get("symbols", [])
    elif isinstance(symbols_data_raw, list):
        symbol_list = symbols_data_raw
    else:
        symbol_list = []

    if not symbol_list:
        print("❌ No symbols received.")
        return StepOutput(content={"transformations": {}, "naming": []})

    # ── Normalise module list ─────────────────────────────────────────────────
    raw_module_list = []
    if isinstance(modules_data_raw, dict) and "modules" in modules_data_raw:
        modules_data_raw = modules_data_raw["modules"]

    if isinstance(modules_data_raw, dict):
        for mod_id, info in modules_data_raw.items():
            raw_module_list.append({
                "module_id":   mod_id,
                "module_name": mod_id,
                "summary":     info.get("summary", ""),
                "symbols":     info.get("symbols", []),
            })
    elif isinstance(modules_data_raw, list):
        for m in modules_data_raw:
            raw_module_list.append({
                "module_id":   m.get("module_id") or m.get("module_name"),
                "module_name": m.get("module_name") or m.get("module_id"),
                "summary":     m.get("summary", ""),
                "symbols":     m.get("symbols", []),
            })

    if isinstance(file_path_raw, dict):
        file_paths = file_path_raw.get("path", [])
    elif isinstance(file_path_raw, list):
        file_paths = file_path_raw
    else:
        file_paths = []

    # ── Deduplicate / validate modules ────────────────────────────────────────
    known_sids: set = {s.get("symbol_id") for s in symbol_list if s.get("symbol_id")}
    seen_names: set = set()
    module_list: list = []

    seen_sym_sets: list[frozenset] = []
    for m in raw_module_list:
        mod_name = m["module_name"]
        mod_sym_ids = frozenset(s for s in m.get("symbols", []) if s in known_sids)
        if not mod_sym_ids:
            print(f"  ⚠️  Skipping phantom module '{mod_name}'")
            continue
        if mod_name in seen_names:
            print(f"  ⚠️  Skipping duplicate module name '{mod_name}'")
            continue
        if mod_sym_ids in seen_sym_sets:
            print(f"  ⚠️  Skipping module '{mod_name}' — identical symbol set already registered")
            continue
        seen_names.add(mod_name)
        seen_sym_sets.append(mod_sym_ids)
        module_list.append(m)

    # ── plan_id map (stable, index-based) ────────────────────────────────────
    sid_to_plan_id = {
        s["symbol_id"]: f"plan_{i:03d}"
        for i, s in enumerate(symbol_list, 1)
        if s.get("symbol_id")
    }

    # ── Hierarchy: skip absorbed symbols to save LLM calls ───────────────────
    kb_thresh = fetch_content.get("hierarchy_thresholds", {})
    _gt       = int(kb_thresh.get("group_threshold", 8)) if kb_thresh else 8
    _rep_sids = _hierarchy_representative_sids(
    symbol_list,
    _gt,
    int(kb_thresh.get("test_threshold", 14)) if kb_thresh else 14,
    )
    # ─────────────────────────────────────────────────────────────────────────

    # ── One LLM call per module ───────────────────────────────────────────────
    transformations: dict = {}
    all_naming: list = []

    # Use hash as primary key so overloaded symbols are processed independently
    sym_by_hash = {
        (meta := s.get("meta_data", s)).get("symbol_hash") or s.get("symbol_hash", s.get("symbol_id")): s
        for s in symbol_list
        if s.get("symbol_id")
    }

    file_path_list = []
    if isinstance(file_paths, list):
        for p in file_paths:
            if isinstance(p, dict):
                fp = (
                    p.get("meta_data", {}).get("file_path")     
                    or p.get("name")
                    or ""
                )
            else:
                fp = str(p)
            if fp:                                               
                file_path_list.append(fp)
    
    file_path_list = sorted(set(file_path_list))   # dedup in case KB has dupes
    logger.info(
        f"Folder structure passed to planning agent "
        f"({len(file_path_list)} paths): {file_path_list}{'...' if len(file_path_list) > 5 else ''}"
    )

    # ── Build hash-based unique symbol registry ───────────────────────────────
    # symbol_hash is unique per symbol even when symbol_id collides
    hash_to_sym: dict[str, dict] = {}
    sid_to_hashes: dict[str, list[str]] = {}  # one sid may map to multiple hashes

    for sym in symbol_list:
        sid  = sym.get("symbol_id")
        meta = sym.get("meta_data", sym)
        h    = meta.get("symbol_hash") or sym.get("symbol_hash")
        if not sid or not h:
            continue
        hash_to_sym[h] = sym
        sid_to_hashes.setdefault(sid, []).append(h)

    sid_to_mod_info: dict[str, dict] = {}
    hash_to_mod_info: dict[str, dict] = {}

    for m in module_list:
        seen_in_module: set[str] = set()
        for sid in m.get("symbols", []):
            hashes = sid_to_hashes.get(sid, [sid])  # fallback to sid if no hash
            for h in hashes:
                if h in seen_in_module:
                    continue
                seen_in_module.add(h)
                if h in hash_to_mod_info:
                    print(f"  ⚠️  Symbol hash '{h}' (sid='{sid}') already claimed by '{hash_to_mod_info[h]['module_name']}' — ignoring '{m['module_name']}'")
                    continue
                hash_to_mod_info[h] = m
            # sid-level mapping still needed for quick lookups
            if sid not in sid_to_mod_info:
                sid_to_mod_info[sid] = m

    # ── One LLM call per symbol ───────────────────────────────────────────────
    for sym in symbol_list:
        sid = sym.get("symbol_id")
        if not sid:
            continue

        mod_info = hash_to_mod_info.get(
            (sym.get("meta_data", sym).get("symbol_hash") or sym.get("symbol_hash", sid)),
            sid_to_mod_info.get(sid, {})
        )
        mod_name    = mod_info.get("module_name", "unknown_module")
        mod_summary = mod_info.get("summary", "")

        print(f"🔹 Analysing symbol: {sid} (module: {mod_name})")
        # ── Skip non-representative hierarchy symbols — no LLM call ──────────
        _t = (
            (sym.get("meta_data", sym).get("ast_node_type") or
             sym.get("meta_data", sym).get("symbol_type") or "")
        ).lower()
        if _t in _HIERARCHY_TYPES and sid not in _rep_sids:
            transformations[sid] = {"transformation": "1:1", "parts": []}
            continue
        # ─────────────────────────────────────────────────────────────────────

        info = analyse_module_symbols(
            mod_name=mod_name,
            mod_summary=mod_summary,
            mod_symbols=[sym],
            plan_id_map=sid_to_plan_id,
            file_paths=file_path_list,
        ).get(sid, {})
        if not isinstance(info, dict):
            logger.warning(
                "Ignoring malformed transformation plan for %s: expected object, got %s",
                sid,
                type(info).__name__,
            )
            info = {}

        try:
            user = current_user.get()
            _send_planning_step_log(
                migration_plan_step_id,
                f"Analysed symbol: {sid} → {info.get('target_symbol_name', sid)} ({info.get('transformation', '1:1')})",
                user,
                migration_plan_msg_group_id,
            )
        except Exception:
            pass

       
        # ── transformations dict ──────────────────────────────────────────────
        meta = sym.get("meta_data", sym)

        symbol_type = (
            meta.get("symbol_type")
            or ""
        ).lower()

        xform_type = info.get("transformation", "1:1")
        parts = info.get("parts", [])

        _CONTAINER_TYPES = {"preamble", "section", "group", "test"}

        if symbol_type in _CONTAINER_TYPES:
            xform_type = "1:1"
            parts = []

        transformations[sid] = {
            "transformation": xform_type,
            "parts": parts,
        }

        # ── naming list ───────────────────────────────────────────────────────
        all_naming.append({
            "symbol_id":          sid,
            "target_symbol_name": info.get("target_symbol_name", sid.split("_")[-1]),
            "target_symbol_type": info.get("target_symbol_type", "symbol"),
            "target_file":        info.get("target_file") or "",
        })

        # ── emit one naming entry per split part too ──────────────────────────
        for part in info.get("parts", []):
            all_naming.append({
                "symbol_id":          sid,
                "part_id":            part.get("part_id"),
                "target_symbol_name": part.get("target_symbol_name"),
                "target_symbol_type": part.get("target_symbol_type", "symbol"),
                "target_file":        info.get("target_file") or "",
            })

    one_to_one = sum(1 for v in transformations.values() if v["transformation"] == "1:1")
    splits = sum(1 for v in transformations.values() if v["transformation"] == "Split")
    print(f"✅ {len(all_naming)} naming entries — {one_to_one}x 1:1, {splits}x split.")

    try:
        user = current_user.get()
        _send_planning_step_result(
            migration_plan_step_id,
            migration_plan_step_name,
            f"Transformation analysis complete: {one_to_one} symbols 1:1, {splits} split, {len(all_naming)} naming entries",
            user,
            migration_plan_msg_group_id,
        )
    except Exception:
        pass

    return StepOutput(content={"transformations": transformations, "naming": all_naming})

def generate_migration_plan(step_input: StepInput) -> StepOutput:
    """
    Step 3: pure-Python plan assembly — no LLM call.
    """
    print("📋 Assembling migration plans (pure Python)...")
    try:
        user = current_user.get()
        _send_planning_step_log(
            migration_plan_step_id,
            "Assembling migration plans from symbols and transformation data...",
            user,
            migration_plan_msg_group_id,
        )
    except Exception:
        pass

    meta_raw = _coerce_step_payload(step_input.get_step_content("get_symbol_module_meta"))
    if not meta_raw.get("symbols_data", {}).get("symbols"):
        meta_raw = _fallback_symbol_module_meta()
    if meta_raw.get("skipped"):
        existing = meta_raw.get("module_plans", {})
        total = sum(len(v.get("plans", [])) for v in existing.values())
        logger.info(f"Plan already exists — returning cached plan: {len(existing)} modules, {total} entries.")
        return StepOutput(content={"module_plans": existing, "output_path": ""})
    if isinstance(meta_raw, str):
        try:    meta_raw = json.loads(meta_raw)
        except Exception: meta_raw = {}

    symbols_raw = meta_raw.get("symbols_data", {}) if isinstance(meta_raw, dict) else {}
    modules_raw = meta_raw.get("modules_data", {}) if isinstance(meta_raw, dict) else {}
    thresholds = meta_raw.get("hierarchy_thresholds",{}) if isinstance(meta_raw, dict) else {}
    dep_step_output = _coerce_step_payload(
        step_input.get_step_content("generate_dependency_plan")
    )
    dep_filename    = dep_step_output.get("filename")

    combined = step_input.get_step_content("generate_symbols_transformation") or "{}"
    if isinstance(combined, str):
        try:    combined = json.loads(combined)
        except Exception: combined = {}

    transformations: dict = combined.get("transformations", {})
    naming_list:     list = combined.get("naming", [])

    # ── Normalise symbol list ─────────────────────────────────────────────────
    if isinstance(symbols_raw, dict):
        symbol_list = symbols_raw.get("symbols", [])
    elif isinstance(symbols_raw, list):
        symbol_list = symbols_raw
    else:
        symbol_list = []

    # ── Normalise module list ─────────────────────────────────────────────────
    if isinstance(modules_raw, dict) and "modules" in modules_raw:
        modules_raw = modules_raw["modules"]

    module_list = []
    if isinstance(modules_raw, dict):
        for mod_id, info in modules_raw.items():
            module_list.append({
                "module_name": mod_id,
                "symbols":     info.get("symbols", []),
            })
    elif isinstance(modules_raw, list):
        for m in modules_raw:
            module_list.append({
                "module_name": m.get("module_name") or m.get("module_id"),
                "symbols":     m.get("symbols", []),
            })

    if not symbol_list:
        print("❌ No symbols — cannot build migration plan.")
        return StepOutput(content={"module_plans": {}})

    if not module_list:
        print("❌ No modules — cannot build migration plan.")
        return StepOutput(content={"module_plans": {}})

    # ── Reference maps ────────────────────────────────────────────────────────
    sym_idx = {s["symbol_id"]: s for s in symbol_list if s.get("symbol_id")}

    sid_to_plan_id = {
        sid: f"plan_{i:03d}"
        for i, sid in enumerate(sym_idx, 1)
    }

    naming_map: dict[str, dict] = {}
    naming_map_short: dict[str, dict] = {}
    for n in naming_list:
        if not isinstance(n, dict):
            continue
        sid = n.get("symbol_id")
        if not sid or n.get("part_id"):
            continue
        naming_map[sid] = n
        naming_map_short[sid.split("_")[-1]] = n

    sid_to_module: dict[str, str] = {}
    for m in module_list:
        for sid in m.get("symbols", []):
            sid_to_module[sid] = m.get("module_name", "")

    short_name_to_sid: dict[str, str] = {}
    for sid in sym_idx:
        short_name_to_sid[sid.split("_")[-1]] = sid

    order_idx = {s["symbol_id"]: i for i, s in enumerate(symbol_list)}

    # ── Generic topo sort ─────────────────────────────────────────────────────
    def topo_sort(nodes: list[str], get_deps: callable) -> list[str]:
        node_set  = set(nodes)
        visited:  set[str] = set()
        in_stack: set[str] = set()
        result:   list[str] = []

        def visit(n: str):
            if n in visited:
                return
            if n in in_stack:
                print(f"Circular dependency detected at '{n}' — skipping")
                return
            in_stack.add(n)
            for dep in get_deps(n):
                if dep in node_set:
                    visit(dep)
            in_stack.discard(n)
            visited.add(n)
            result.append(n)

        for n in sorted(nodes):
            visit(n)
        return result

    # ── Call extraction — language agnostic ───────────────────────────────────
    _CALL_RE = re.compile(
        r'(?:\w+::)+(\w+)\s*\('
        r'|(?:\w+\.)+(\w+)\s*\('
        r'|(?:\w+->)+(\w+)\s*\('
        r'|\b(\w+)\s*\('
    )

    def _extract_calls_from_source(file_path: str, start: int, end: int) -> list[str]:
        src = read_source_lines(file_path, start, end)
        if not src:
            return []
        names = set()
        for m in _CALL_RE.finditer(src):
            name = next((g for g in m.groups() if g is not None), None)
            if name:
                names.add(name)
        return list(names)

    def _resolve_sid(call_name: str) -> str | None:
        if call_name in sid_to_plan_id:
            return call_name
        if call_name in short_name_to_sid:
            return short_name_to_sid[call_name]
        bare = re.split(r'::|\.|\->', call_name)[-1]
        return short_name_to_sid.get(bare)

    def _get_resolved_callees(sid: str) -> list[str]:
        """Single source of truth for resolving what a symbol calls."""
        sym  = sym_idx.get(sid, {})
        meta = sym.get("meta_data", sym)
        found: set[str] = set()

        # 1. dependencies field — resolved full symbol_ids, most reliable
        for dep in meta.get("dependencies", []):
            if not isinstance(dep, dict) or not dep.get("resolved", False):
                continue
            resolved = _resolve_sid(dep.get("target", ""))
            if resolved and resolved != sid:
                found.add(resolved)

        # 2. calls field — short names, fallback
        for call in meta.get("calls", []):
            name     = call.get("name") if isinstance(call, dict) else str(call)
            resolved = _resolve_sid(name)
            if resolved and resolved != sid:
                found.add(resolved)

        # 3. source parsing — last resort
        if not found:
            file_path = meta.get("file_path") or sym.get("file_path", "")
            lr        = meta.get("line_range") or sym.get("line_range") or {}
            start     = lr.get("start", 0)
            end       = lr.get("end", 0)
            if file_path and start and end:
                for name in _extract_calls_from_source(file_path, start, end):
                    resolved = _resolve_sid(name)
                    if resolved and resolved != sid:
                        found.add(resolved)
                if found:
                    print(f"{sid}: used source fallback, found {len(found)} callees")

        return list(found)

    def _get_deps_as_plan_pointers(sid: str, own_plan_id: str) -> list[str]:
        """Returns cross-plan dependency pointers for plan assembly."""
        result = []
        for callee_sid in _get_resolved_callees(sid):
            if callee_sid not in sid_to_plan_id:
                continue

            callee_plan = sid_to_plan_id[callee_sid]

            if callee_plan == own_plan_id:
                continue

            # Only keep plan_id (no module prefix)
            result.append(callee_plan)

        return sorted(set(result))

    def _get_deps_as_sids(sid: str) -> list[str]:
        """Returns callee symbol_ids for topo_sort on symbols."""
        return [s for s in _get_resolved_callees(sid) if s in sym_idx]
    
    def _split_path(path: str) -> tuple[str, str]:
        if not path:
            return "", ""
        return path, os.path.basename(path)
    
    def _to_relative(abs_path: str) -> str:
        if not abs_path:
            return abs_path
        try:
            source_root = Path(source_path_ctx.get(""))
            base = source_root.parent  # one level up → includes root folder name in path
            return Path(abs_path).relative_to(base).as_posix()
        except ValueError:
            return Path(abs_path).name
        
    def _get_hierarchy_thresholds() -> tuple[int, int, int]:
        """
        Compute adaptive hierarchy thresholds.

        Small samples:
            median-based thresholds

        Large samples:
            mean + 2σ

        Returns:
            (group_threshold,
            test_threshold,
            test_batch_size)
        """

        groups_per_sec: list[int] = []
        tests_per_grp: list[int] = []

        for sid, sym in sym_idx.items():

            meta = sym.get("meta_data", sym)

            t = (
                meta.get("ast_node_type")
                or meta.get("symbol_type")
                or ""
            ).lower()

            if t == "section":

                # groups per section 
                gc = sum(
                    1
                    for s in sym_idx.values()
                    if (
                        (s.get("meta_data", s).get("ast_node_type") or
                        s.get("meta_data", s).get("symbol_type") or "")
                        .lower() == "group"
                    )
                    and s.get("meta_data", s).get("parent_symbol") == sid
                )

                if gc > 0:
                    groups_per_sec.append(gc)

            elif t == "group":

                # tests per group 
                tc = sum(
                    1
                    for s in sym_idx.values()
                    if (
                        (s.get("meta_data", s).get("ast_node_type") or
                        s.get("meta_data", s).get("symbol_type") or "")
                        .lower() == "test"
                    )
                    and s.get("meta_data", s).get("parent_symbol") == sid
                )

                if tc > 0:
                    tests_per_grp.append(tc)

        groups_per_sec = [x for x in groups_per_sec if x > 0]
        tests_per_grp  = [x for x in tests_per_grp if x > 0]

        if not groups_per_sec or not tests_per_grp:
            return (8,14,4)

        sample_count = len(tests_per_grp)

        if sample_count < 15:

            group_threshold = max(
                4,
                min(
                    12,
                    round(_median(groups_per_sec) * 2)
                )
            )

            test_threshold = max(
                8,
                min(
                    25,
                    round(_median(tests_per_grp) * 3)
                )
            )

        else:

            g_std = (
                _stdev(groups_per_sec)
                if len(groups_per_sec) > 1
                else 0.0
            )

            t_std = (
                _stdev(tests_per_grp)
                if len(tests_per_grp) > 1
                else 0.0
            )

            group_threshold = max(
                4,
                min(
                    12,
                    round(
                        _mean(groups_per_sec)
                        + 2 * g_std
                    )
                )
            )

            test_threshold = max(
                8,
                min(
                    25,
                    round(
                        _mean(tests_per_grp)
                        + 2 * t_std
                    )
                )
            )

        test_batch_size = max(
            4,
            min(
                round(test_threshold / 2),
                round(_mean(tests_per_grp))
            )
        )

        logger.info(
            f"Hierarchy thresholds:"
            f" sections={len(groups_per_sec)},"
            f" groups={len(tests_per_grp)} → "
            f"group≤{group_threshold}, "
            f"test≤{test_threshold}, "
            f"batch={test_batch_size}"
        )

        return (
            group_threshold,
            test_threshold,
            test_batch_size
        )

    # ── Derive thresholds from actual project data ────────────────────────

    if thresholds:
        _GROUP_THRESHOLD = thresholds.get(
            "group_threshold",
            8
        )
        _TEST_THRESHOLD = thresholds.get(
            "test_threshold",
            14
        )
        _TEST_BATCH_SIZE = thresholds.get(
            "test_batch_size",
            4
        )

        logger.info(
            f"Using KB hierarchy thresholds: "
            f"{_GROUP_THRESHOLD}, "
            f"{_TEST_THRESHOLD}, "
            f"{_TEST_BATCH_SIZE}"
        )
    else:
        (
            _GROUP_THRESHOLD,
            _TEST_THRESHOLD,
            _TEST_BATCH_SIZE,
        ) = _get_hierarchy_thresholds()

    _HIERARCHY_TYPES = {"preamble", "section", "group", "test", "teardown"}

    def _is_hierarchy_module(sids: list) -> bool:
        """
        Mirror _build_hierarchy's type detection exactly —
        fall back to symbol_type when ast_node_type is absent.
        """
        for s in sids:
            sym  = sym_idx.get(s, {})
            meta = sym.get("meta_data", sym)
            t    = (meta.get("ast_node_type") or meta.get("symbol_type") or "").lower()
            if t in _HIERARCHY_TYPES:
                return True
        return False

    def _build_hierarchy(sids: list) -> dict:
        """Rebuild section→group→test from parent_symbol relationships."""
        result = {"preamble": None, "teardown": None, "sections": {}}

        for sid in sids:
            sym  = sym_idx.get(sid, {})
            meta = sym.get("meta_data", sym)
            t    = (meta.get("ast_node_type") or meta.get("symbol_type") or "").lower()
            if   t == "preamble":  result["preamble"] = sym
            elif t == "teardown":  result["teardown"] = sym
            elif t == "section":   result["sections"][sid] = {"sym": sym, "groups": {}}

        for sid in sids:
            sym    = sym_idx.get(sid, {})
            meta   = sym.get("meta_data", sym)
            t      = (meta.get("ast_node_type") or meta.get("symbol_type") or "").lower()
            parent = meta.get("parent_symbol", "")
            if t == "group" and parent in result["sections"]:
                result["sections"][parent]["groups"][sid] = {"sym": sym, "tests": []}

        for sid in sids:
            sym    = sym_idx.get(sid, {})
            meta   = sym.get("meta_data", sym)
            t      = (meta.get("ast_node_type") or meta.get("symbol_type") or "").lower()
            parent = meta.get("parent_symbol", "")
            if t == "test":
                for sec_data in result["sections"].values():
                    if parent in sec_data["groups"]:
                        sec_data["groups"][parent]["tests"].append(sym)
                        break

        return result

    def _hierarchy_plan_entry(sym, plan_id, line_range_override=None, name_override=None):
        """Build a single plan entry for a hierarchy symbol."""
        meta               = sym.get("meta_data", sym)
        sid                = meta.get("symbol_id") or sym.get("symbol_id", "")
        symbol_hash   = meta.get("symbol_hash") or sym.get("symbol_hash", "")   # ADD
        original_name      = name_override or sym.get("name") or meta.get("symbol_name") or sid
        naming             = naming_map.get(sid) or naming_map_short.get(sid.split("_")[-1], {})
        target_symbol_name = naming.get("target_symbol_name") or original_name
        target_file        = (naming.get("target_file") or "").strip()
        file_path          = meta.get("file_path") or sym.get("file_path", "")
        source_lr          = line_range_override or meta.get("line_range") or {"start": 0, "end": 0}
        deps               = _get_deps_as_plan_pointers(sid, plan_id)
        src_path, src_name = _split_path(_to_relative(file_path))
        tgt_path, tgt_name = _split_path(target_file)
        return {
            "plan_id":            plan_id,
            "symbol_id":          sid,
            "symbol_name":        original_name,
            "symbol_hash":        symbol_hash,
            "goals":              f"Convert {original_name} to {target_symbol_name} as per target system requirements",
            "module":             mod_name,
            "transformation":     "1:1",
            "target_symbol_name": target_symbol_name,
            "target_file":        target_file,
            "source_file_path":   src_path,
            "source_file_name":   src_name,
            "target_file_path":   tgt_path,
            "target_file_name":   tgt_name,
            "source_line_range":  source_lr,
            "file_path":          file_path,
            "depends_on_plans":   deps,
            MigrationConstants.MIGRATION_STATUS: MigrationConstants.STATUS_PENDING,
        }

    def _assemble_hierarchy_plans(sids: list) -> tuple[list, set]:
        """
        Threshold-based plan assembly for test hierarchy modules.
        Returns (plan_entries, consumed_sids).
        """
        hierarchy  = _build_hierarchy(sids)
        entries    = []
        consumed   = set()

        # Preamble — always its own plan
        if hierarchy["preamble"]:
            sym = hierarchy["preamble"]
            sid = (sym.get("meta_data", sym).get("symbol_id") or sym.get("symbol_id", ""))
            pid = sid_to_plan_id.get(sid)
            if pid and sid not in emitted_sids:
                entries.append(_hierarchy_plan_entry(sym, pid))
                consumed.add(sid)

        # Sections with threshold logic
        for sec_id, sec_data in hierarchy["sections"].items():
            sec_sym = sec_data["sym"]
            groups  = sec_data["groups"]

            if sec_id in emitted_sids:
                continue

            if len(groups) <= _GROUP_THRESHOLD:
                pid = sid_to_plan_id.get(sec_id)
                if pid:
                    # Collect all child sids this section plan will absorb
                    child_sids: list[str] = [sec_id]
                    for grp_id, grp_data in groups.items():
                        child_sids.append(grp_id)
                        for tst_sym in grp_data["tests"]:
                            child_sids.append(
                                tst_sym.get("meta_data", tst_sym).get("symbol_id")
                                or tst_sym.get("symbol_id", "")
                            )

                    # Aggregate deps from all children, excluding intra-plan refs
                    aggregated_deps: set[str] = set()
                    for child_sid in child_sids:
                        for dep_plan_id in _get_deps_as_plan_pointers(child_sid, pid):
                            aggregated_deps.add(dep_plan_id)

                    entry = _hierarchy_plan_entry(sec_sym, pid)
                    entry["depends_on_plans"] = sorted(aggregated_deps)
                    entries.append(entry)

                    for sid in child_sids:
                        consumed.add(sid)
            else:
                # ── Group-level: one plan per group (or batched tests) ─────────
                consumed.add(sec_id)   # section itself absorbed into groups
                for grp_id, grp_data in groups.items():
                    if grp_id in emitted_sids:
                        continue
                    grp_sym = grp_data["sym"]
                    tests   = grp_data["tests"]

                    if len(tests) <= _TEST_THRESHOLD:
                        pid = sid_to_plan_id.get(grp_id)
                        if pid:
                            child_sids = [grp_id] + [
                                tst_sym.get("meta_data", tst_sym).get("symbol_id")
                                or tst_sym.get("symbol_id", "")
                                for tst_sym in tests
                            ]
                            aggregated_deps: set[str] = set()
                            for child_sid in child_sids:
                                for dep_plan_id in _get_deps_as_plan_pointers(child_sid, pid):
                                    aggregated_deps.add(dep_plan_id)

                            entry = _hierarchy_plan_entry(grp_sym, pid)
                            entry["depends_on_plans"] = sorted(aggregated_deps)
                            entries.append(entry)

                            for sid in child_sids:
                                consumed.add(sid)
                    else:
                        # Batch tests: N per plan
                        consumed.add(grp_id)
                        grp_meta = grp_sym.get("meta_data", grp_sym)
                        grp_name = grp_meta.get("name") or grp_meta.get("symbol_name") or "batch"

                        for b_idx in range(0, len(tests), _TEST_BATCH_SIZE):
                            batch      = tests[b_idx: b_idx + _TEST_BATCH_SIZE]
                            batch_num  = b_idx // _TEST_BATCH_SIZE + 1
                            first_meta = batch[0].get("meta_data", batch[0])
                            last_meta  = batch[-1].get("meta_data", batch[-1])
                            batch_lr   = {
                                "start": (first_meta.get("line_range") or {}).get("start", 0),
                                "end":   (last_meta.get("line_range") or {}).get("end",   0),
                            }
                            # use first test's plan_id for the batch
                            first_sid = first_meta.get("symbol_id") or batch[0].get("symbol_id", "")
                            pid = sid_to_plan_id.get(first_sid)
                            if pid:
                                batch_name = f"{grp_name}_batch_{batch_num}"
                                entries.append(
                                    _hierarchy_plan_entry(
                                        grp_sym, pid,
                                        line_range_override=batch_lr,
                                        name_override=batch_name,
                                    )
                                )
                            for tst_sym in batch:
                                consumed.add(
                                    tst_sym.get("meta_data", tst_sym).get("symbol_id")
                                    or tst_sym.get("symbol_id", "")
                                )

        # Teardown — always its own plan
        if hierarchy["teardown"]:
            sym = hierarchy["teardown"]
            sid = (sym.get("meta_data", sym).get("symbol_id") or sym.get("symbol_id", ""))
            pid = sid_to_plan_id.get(sid)
            if pid and sid not in emitted_sids:
                entries.append(_hierarchy_plan_entry(sym, pid))
                consumed.add(sid)

        return entries, consumed

    # ── Sequential plan ID counter — resets per migration, not per module ────
    _plan_seq = [1]

    def _next_plan_id() -> str:
        pid = f"plan_{_plan_seq[0]:03d}"
        _plan_seq[0] += 1
        return pid
    # ─────────────────────────────────────────────────────────────────────────

    # ── Assemble per-module plans ─────────────────────────────────────────────
    all_module_plans: dict[str, dict] = {}
    emitted_sids: set[str] = set()

    for m in module_list:
        mod_name    = m.get("module_name", "unknown_module")
        primary_ids = [sid for sid in m.get("symbols", []) if sid in sym_idx]

        if not primary_ids:
            print(f"  ⚠️  {mod_name}: no matching symbols — skipping.")
            continue

        plan_entries = []

        def _complexity(sid: str) -> float:
            sym  = sym_idx.get(sid, {})
            meta = sym.get("meta_data", sym)
            return float(meta.get("complexity") or sym.get("complexity") or 0.0)

        def _dep_count(sid: str) -> int:
            """Number of resolved outbound dependencies — lower = more utility-like."""
            return len(_get_resolved_callees(sid))

        sorted_sids = topo_sort(
            sorted(primary_ids, key=lambda s: (
                0 if _dep_count(s) == 0 else 1,   # tier 0: utilities strictly first
                _dep_count(s),                      # within tier 1: fewer deps first
                -_complexity(s),                    # tiebreaker: simpler first
                order_idx.get(s, 9999),
            )),
            get_deps=_get_deps_as_sids,
        )

        # ── Hierarchy modules use threshold-based assembly ────────────────
        if _is_hierarchy_module(primary_ids):
            hierarchy_entries, consumed_sids = _assemble_hierarchy_plans(primary_ids)

            # ── Renumber + dependency remap to final hierarchy plans ───────────────

            old_to_new: dict[str, str] = {}

            # maps every absorbed symbol -> final emitted plan id
            sid_to_final_plan: dict[str, str] = {}

            for entry in hierarchy_entries:
                old_pid = entry["plan_id"]

                if old_pid not in old_to_new:
                    old_to_new[old_pid] = _next_plan_id()

                new_pid = old_to_new[old_pid]
                entry["plan_id"] = new_pid

                sid = entry["symbol_id"]
                sid_to_final_plan[sid] = new_pid


            # Add child symbols absorbed into section/group plans
            hierarchy = _build_hierarchy(primary_ids)

            for sec_id, sec_data in hierarchy["sections"].items():

                sec_pid = sid_to_final_plan.get(sec_id)

                if not sec_pid:
                    continue

                for grp_id, grp_data in sec_data["groups"].items():

                    sid_to_final_plan[grp_id] = sec_pid

                    for tst_sym in grp_data["tests"]:
                        tst_sid = (
                            tst_sym.get("meta_data", tst_sym).get("symbol_id")
                            or tst_sym.get("symbol_id")
                        )

                        if tst_sid:
                            sid_to_final_plan[tst_sid] = sec_pid


            # rebuild dependencies using ALL absorbed symbols

            for entry in hierarchy_entries:

                final_deps = set()

                plan_pid = entry["plan_id"]

                contributing_sids = [
                    sid
                    for sid, mapped_pid in sid_to_final_plan.items()
                    if mapped_pid == plan_pid
                ]

                for source_sid in contributing_sids:

                    for dep_sid in _get_resolved_callees(source_sid):

                        dep_pid = sid_to_final_plan.get(dep_sid)

                        if dep_pid and dep_pid != plan_pid:
                            final_deps.add(dep_pid)

                entry["depends_on_plans"] = sorted(final_deps)
                entry["covered_symbol_ids"] = sorted(
                    sid for sid, mapped_pid in sid_to_final_plan.items()
                    if mapped_pid == plan_pid
                )

            # ────────────────────────────────────────────────────────────────────────

            plan_entries.extend(hierarchy_entries)
            emitted_sids.update(consumed_sids)

            # Fallback: orphaned symbols whose parent_symbol wasn't matched
            for sid in primary_ids:
                if sid in emitted_sids:
                    continue
                sym  = sym_idx[sid]
                meta = sym.get("meta_data", sym)
                original_name = sym.get("symbol_name") or meta.get("symbol_name") or sid.split("_")[-1]
                pid = _next_plan_id()
                logger.warning(f"Orphaned hierarchy symbol '{sid}' — emitting fallback plan {pid}")
                file_path = meta.get("file_path") or sym.get("file_path", "")
                source_lr = meta.get("line_range") or sym.get("line_range") or {"start": 0, "end": 0}
                src_path, src_name = _split_path(_to_relative(file_path))
                plan_entries.append({
                    "plan_id":            pid,
                    "symbol_id":          sid,
                    "symbol_name":        original_name,
                    "symbol_hash":        symbol_hash,
                    "goals":              f"Convert {original_name} (orphaned hierarchy symbol)",
                    "module":             mod_name,
                    "transformation":     "1:1",
                    "target_symbol_name": original_name,
                    "target_file":        "",
                    "source_file_path":   src_path,
                    "source_file_name":   src_name,
                    "target_file_path":   "",
                    "target_file_name":   "",
                    "source_line_range":  source_lr,
                    "file_path":          file_path,
                    "depends_on_plans":   _get_deps_as_plan_pointers(sid, pid),
                    "covered_symbol_ids": [sid],
                    MigrationConstants.MIGRATION_STATUS: MigrationConstants.STATUS_PENDING,
                })
                emitted_sids.add(sid)

        else:
            # ── Regular symbols: existing 1:1 / Split logic ─────────────
            for sid in sorted_sids:
                if sid in emitted_sids:
                    print(f"  ⚠️  Skipping duplicate symbol '{sid}' in module '{mod_name}'")
                    continue
                emitted_sids.add(sid)

                sym         = sym_idx[sid]
                meta        = sym.get("meta_data", sym)
                xform       = transformations.get(sid, {"transformation": "1:1", "parts": []})
                symbol_hash = meta.get("symbol_hash") or sym.get("symbol_hash", "")
                plan_id  = sid_to_plan_id[sid]
                naming   = naming_map.get(sid) or naming_map_short.get(sid.split("_")[-1], {})

                original_name = (
                    sym.get("symbol_name")
                    or meta.get("symbol_name")
                    or sid.split("_")[-1]
                )
                target_symbol_name = naming.get("target_symbol_name") or ""
                file_path          = meta.get("file_path") or sym.get("file_path", "")
                target_file        = (naming.get("target_file") or "").strip()

                if not target_file:
                    print(f"  ⚠️  Empty target_file for {sid} — check agent output")

                source_lr   = meta.get("line_range") or sym.get("line_range") or {"start": 0, "end": 0}
                deps        = _get_deps_as_plan_pointers(sid, plan_id)
                symbol_goal = f"Convert {original_name} to {target_symbol_name} as per target system requirements".strip()
                is_split    = xform["transformation"] == "Split"
                parts       = xform.get("parts", [])

                src_path, src_name = _split_path(_to_relative(meta.get("file_path") or sym.get("file_path", "")))
                tgt_path, tgt_name = _split_path(target_file)

                if is_split and not parts:
                    print(f"  ❌  {sid} is Split but has no parts — marking as error")
                    plan_entries.append({
                        "plan_id":            plan_id,
                        "symbol_id":          sid,
                        "symbol_name":        original_name,
                        "symbol_hash":        symbol_hash,
                        "goals":              symbol_goal,
                        "module":             mod_name,
                        "transformation":     "Split",
                        "target_symbol_name": target_symbol_name,
                        "target_file":        target_file,
                        "source_file_path":   src_path,
                        "source_file_name":   src_name,
                        "target_file_path":   tgt_path,
                        "target_file_name":   tgt_name,
                        "source_line_range":  source_lr,
                        "file_path":          file_path,
                        "depends_on_plans":   deps,
                        "covered_symbol_ids": [sid],
                        MigrationConstants.MIGRATION_STATUS: MigrationConstants.STATUS_ERROR,
                        AgentConstants.TASK_ERROR: MigrationConstants.SPLIT_TRANSFORMATION_MISSING_PARTS,
                    })
                elif not is_split:
                    plan_entries.append({
                        "plan_id":            plan_id,
                        "symbol_id":          sid,
                        "symbol_name":        original_name,
                        "symbol_hash":        symbol_hash,
                        "goals":              symbol_goal,
                        "module":             mod_name,
                        "transformation":     xform["transformation"],
                        "target_symbol_name": target_symbol_name,
                        "target_file":        target_file,
                        "source_file_path":   src_path,
                        "source_file_name":   src_name,
                        "target_file_path":   tgt_path,
                        "target_file_name":   tgt_name,
                        "source_line_range":  source_lr,
                        "file_path":          file_path,
                        "depends_on_plans":   deps,
                        "covered_symbol_ids": [sid],
                        MigrationConstants.MIGRATION_STATUS: MigrationConstants.STATUS_PENDING,
                    })
                else:
                    total_parts_count = len(parts)
                    for part in parts:
                        plan_entries.append({
                            "plan_id":            part.get("part_id", f"{plan_id}_part"),
                            "symbol_id":          sid,
                            "symbol_name":        original_name,
                            "symbol_hash":        symbol_hash,
                            "goals":              symbol_goal,
                            "module":             mod_name,
                            "transformation":     "Split",
                            "target_symbol_name": part.get("target_symbol_name", target_symbol_name),
                            "target_file":        target_file,
                            "source_file_path":   src_path,
                            "source_file_name":   src_name,
                            "target_file_path":   tgt_path,
                            "target_file_name":   tgt_name,
                            "source_line_range": {
                                "start": part.get("start_line", source_lr.get("start", 0)),
                                "end":   part.get("end_line",   source_lr.get("end",   0)),
                            },
                            "file_path":          file_path,
                            "depends_on_plans":   deps,
                            "covered_symbol_ids": [sid],
                            "migration_status":   "pending",
                            "total_parts":        total_parts_count,
                        })

        all_module_plans[mod_name] = {
            "goals": f"Processing the {mod_name} module conversion",
            "plans": plan_entries,
        }
        print(f"  ✅ {mod_name}: {len(plan_entries)} plan entries")
        try:
            user = current_user.get()
            _send_planning_step_log(
                migration_plan_step_id,
                f"Module '{mod_name}': {len(plan_entries)} plan entries generated",
                user,
                migration_plan_msg_group_id,
            )
        except Exception:
            pass

    # A module label may be incomplete or malformed. Never let that omit a
    # scanned symbol from conversion: emit an explicit fallback plan instead.
    uncovered_sids = set(sym_idx) - emitted_sids
    if uncovered_sids:
        fallback_module = "unassigned_source_symbols"
        fallback_plans = all_module_plans.setdefault(
            fallback_module,
            {"goals": "Convert source symbols not assigned to a detected module", "plans": []},
        )["plans"]
        for sid in sorted(uncovered_sids, key=lambda value: order_idx.get(value, 9999)):
            sym = sym_idx[sid]
            meta = sym.get("meta_data", sym)
            name = sym.get("symbol_name") or meta.get("symbol_name") or sid.split("_")[-1]
            file_path = meta.get("file_path") or sym.get("file_path", "")
            src_path, src_name = _split_path(_to_relative(file_path))
            fallback_plans.append({
                "plan_id": _next_plan_id(),
                "symbol_id": sid,
                "symbol_name": name,
                "symbol_hash": meta.get("symbol_hash") or sym.get("symbol_hash", ""),
                "goals": f"Convert {name} (fallback: no module assignment)",
                "module": fallback_module,
                "transformation": "1:1",
                "target_symbol_name": name,
                "target_file": "",
                "source_file_path": src_path,
                "source_file_name": src_name,
                "target_file_path": "",
                "target_file_name": "",
                "source_line_range": meta.get("line_range") or sym.get("line_range") or {"start": 0, "end": 0},
                "file_path": file_path,
                "depends_on_plans": _get_deps_as_plan_pointers(sid, ""),
                "covered_symbol_ids": [sid],
                MigrationConstants.MIGRATION_STATUS: MigrationConstants.STATUS_PENDING,
            })
            emitted_sids.add(sid)
        logger.warning("Added %d fallback plan(s) for unassigned source symbols", len(uncovered_sids))

    # ── Sort modules: dependencies before dependents ──────────────────────────
    def _get_mod_deps(mod_name: str) -> list[str]:
        """Returns dependent module names for topo_sort on modules."""
        deps = set()
        for entry in all_module_plans.get(mod_name, {}).get("plans", []):
            for dep_plan_id in entry.get("depends_on_plans", []):
                # Scan all other modules to find which one owns this plan_id
                for other_mod, other_data in all_module_plans.items():
                    if other_mod == mod_name:
                        continue
                    if any(p["plan_id"] == dep_plan_id for p in other_data.get("plans", [])):
                        deps.add(other_mod)
                        break
        return sorted(deps)

    def _module_avg_complexity(mod_name: str) -> float:
        """Average symbol complexity across a module — lower = more utility-like."""
        plans = all_module_plans.get(mod_name, {}).get("plans", [])
        if not plans:
            return 0.0
        scores = []
        for entry in plans:
            sid = entry.get("symbol_id", "")
            sym  = sym_idx.get(sid, {})
            meta = sym.get("meta_data", sym)
            scores.append(float(meta.get("complexity") or sym.get("complexity") or 0.0))
        return sum(scores) / len(scores) if scores else 0.0

    def _module_total_deps(mod_name: str) -> int:
        """Total cross-module dependencies — lower = more utility-like."""
        return sum(
            len(e.get("depends_on_plans", []))
            for e in all_module_plans.get(mod_name, {}).get("plans", [])
        )

    sorted_mods = topo_sort(
        sorted(
            list(all_module_plans.keys()),
            key=lambda m: (
                _module_total_deps(m),       # fewer cross-deps first (utilities)
                -_module_avg_complexity(m),  # higher avg complexity last
            ),
        ),
        get_deps=_get_mod_deps,
    )
    all_module_plans = {m: all_module_plans[m] for m in sorted_mods if m in all_module_plans}

    # ── Validate no duplicate plan_ids ────────────────────────────────────────
    seen_plan_ids: set[str] = set()
    for mod_name, mod_data in all_module_plans.items():
        for entry in mod_data["plans"]:
            pid = entry["plan_id"]
            if pid in seen_plan_ids:
                print(f"  ❌  Duplicate plan_id '{pid}' found in module '{mod_name}'")
            seen_plan_ids.add(pid)

    # ── Inject dependency file plan entry ─────────────────────────────────

    if dep_filename:
        first_mod = next(iter(all_module_plans))
        all_module_plans[first_mod]["plans"].insert(0, {
            "plan_id":            "plan_dep_000",
            "symbol_id":          "dependency_file",
            "symbol_name":        "N/A",
            "symbol_hash":        "N/A",   # ← add to both non-split and split entries
            "goals":              f"Dependency file: {dep_filename}",
            "module":             first_mod,
            "transformation":     "dependency_file",
            "target_symbol_name": dep_filename,
            "target_file":        dep_filename,
            "source_file_path":   "",
            "source_file_name":   "",
            "target_file_path":   dep_filename,
            "target_file_name":   dep_filename,
            "source_line_range":  {"start": 0, "end": 0},
            "file_path":          "",
            "depends_on_plans":   [],
            "migration_status":   "dependency_file",
        })
        logger.info(f"Injected dependency file plan entry: {dep_filename}")
    else:
        logger.warning("No dependency file output from inject_dependency_file_plan step — skipping injection")
    # ──────────────────────────────────────────────────────────────────────

    # Hard safety gate: plan coverage must include every scanned source symbol.
    # This prevents a seemingly successful migration from silently losing code.
    covered_sids = {
        covered_sid
        for module_data in all_module_plans.values()
        for entry in module_data.get("plans", [])
        for covered_sid in entry.get("covered_symbol_ids", [entry.get("symbol_id")])
        if covered_sid and covered_sid != "dependency_file"
    }
    missing_sids = set(sym_idx) - covered_sids
    if missing_sids:
        raise RuntimeError(
            "Migration plan coverage validation failed; source symbols missing from conversion plan: "
            + ", ".join(sorted(missing_sids))
        )
    logger.info("Migration plan coverage verified: %d/%d source symbols represented", len(covered_sids), len(sym_idx))

    # ── Persist ───────────────────────────────────────────────────────────────
    output_dir  = get_migration_directory()
    output_path = os.path.join(output_dir, "migration_plan.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_module_plans, f, indent=2, ensure_ascii=False)

    print(f"✅ Migration plan written to {output_path}")

    migration_name = migration_name_ctx.get("")
    if migration_name:
        try:
            _plan_user = current_user.get()
            _plan_user_id = _plan_user.id if _plan_user else None
        except Exception:
            _plan_user_id = None
        try:
            get_json_artifact_repository().save_json_artifact(
                migration_name, ArtifactType.MIGRATION_PLAN, all_module_plans, user_id=_plan_user_id
            )
            logger.info("Saved migration_plan to DB artifact store")
        except Exception as _exc:
            logger.warning("Failed to save migration_plan to DB: %s", _exc)

    total_plans = sum(len(v.get("plans", [])) for v in all_module_plans.values())
    try:
        user = current_user.get()
        _send_planning_step_result(
            migration_plan_step_id,
            migration_plan_step_name,
            f"Migration plan written — {len(all_module_plans)} modules, {total_plans} plan entries → {output_path}",
            user,
            migration_plan_msg_group_id,
        )
    except Exception:
        pass
    return StepOutput(content={"module_plans": all_module_plans, "output_path": output_path})
