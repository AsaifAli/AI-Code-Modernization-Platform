import uuid
import os
import shutil
import json
import re
import logging
from pathlib import Path
from textwrap import dedent
from collections import Counter, defaultdict
from typing import Dict, List, Any, Optional, Tuple
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from app.infrastructure.repositories.prompt_repository import fetch_prompt_from_db
from app.infrastructure.utils.ctags_scanner import _build_symbol_id, _stable_hash
from app.infrastructure.utils.file_utils import get_migration_directory
from app.infrastructure.utils.file_utils import (
    read_json_file,
    _collect_convertible_files,
    _apply_rule_based_exclusions,
    _get_runtime_tech_context,
    _LANGUAGE_MAP as language_map,
    _FILENAME_LANGUAGE_MAP as filename_map,
    EXACT_FILENAMES as ext_file,
)
from app.infrastructure.utils.ctag_engine import parse, ParseRequest, FilePayload
from app.application.agents.utility_agent import utility_agent
from app.infrastructure.utils.ctags_scanner import *
from app.application.agents.scanner.scanner_agent import tech_detector
from app.infrastructure.utils.Constants.app_constants import AgentConstants, Constants
from app.infrastructure.utils.user_context import current_user
from app.infrastructure.utils.Constants.agent_event import AgentEventMessages
from app.infrastructure.repositories.source_analyzer_repo import SourceAnalyzerRepo
from app.infrastructure.utils.enums.msg_group import MsgGroup
from app.infrastructure.utils.enums.migration_event import MigrationEvent
from app.infrastructure.utils.Constants.prompt_constants import PromptConstants as PC
from app.infrastructure.utils.Constants.prompt_messages import PromptMessages as PM
from app.infrastructure.utils.migration_context import migration_name_ctx,target_language_ctx
from app.infrastructure.repositories.json_artifact_repository import fetch_json_artifact as _fetch_artifact
from app.infrastructure.utils.Constants.app_constants import ArtifactType
from app.infrastructure.utils.token_tracker import track_tokens
from app.infrastructure.utils.event_helper import MigrationEventHelper
from dotenv import load_dotenv
from statistics import mean as _mean, median as _median, stdev as _stdev
from app.infrastructure.utils.Constants.scanner_contants import ScannerConstants as SC

load_dotenv()
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# WITH THIS:
__all__ = [
    # Core scan pipeline
    "generate_migration_summary",
    "detect_source_language",
    "get_non_convertible_files",
    "_detect_primary_language",
    "_detect_tech_stack",
    "_detect_full_tech_stack_with_llm",
    "_build_base_tech_data",
    "_merge_tech_with_llm_results",
    "_enrich_tech_statically",
    "_generate_or_load_project_graph",
    "_parse_convertible_files",
    "_analyze_project",
    "_get_or_create_non_convertible_files",
    "_get_root_files",
    "_collect_folder_structure",
    "_collect_file_paths",
    "_detect_configuration_files",
    "_collect_config_file_contents",
    "get_folder_structure",
    # Complexity + module graph helpers
    "compute_ast_complexity",
    "generate_module_label",
    "detect_file_scope_ids",
    "build_role_domain_extractor",
    "compute_adaptive_threshold",
    "nx_name_from_igraph",
    # Scanner pipeline internals
    "_process_semantic_ir_batches",
    # "_prepare_output_paths",
    # "_all_scanner_outputs_present",
    # "_build_cached_output_message",
    # "_collect_scan_statistics",
    # "_log_scan_statistics",
    # "_build_success_message",
    # workflow event stream
    "_send_step_start",
    "_send_step_description",
    "_send_step_log",
    "_send_step_result",
    "_send_step_error",
    "_notify_scanner_start",
    "_send_language_event",
    "_send_framework_event",
    "_send_final_scan_metrics",
    "_send_migration_summary",
    "_send_target_response",
    "_notify_migration_table"
]

USE_SEMANTIC_AST = True
USE_AGENT_LANGUAGE_INFERENCE = True
USE_AGENT_DEPENDENCY_EXTRACTION = True
USE_FALLBACK_BUILTIN_LANGUAGE_MAP = True
USE_FALLBACK_BUILTIN_DEP_PATTERNS = True
_language_cache: Dict[str, str] = {}

# -------------------------------------- File Utils -------------------------------------------

def _map_language_to_ts_identifier(raw: str) -> Optional[str]:
    """
    Map any raw language name / file extension / alias to a canonical
    static language-extension mapping identifier using the static dictionary.
    Returns None if unmappable (caller should fall back to LLM).
    """
    if not raw or not isinstance(raw, str):
        return None
    key = raw.strip().lower().lstrip(".")
    return language_map.get(key)

def _compute_plan_completion(plan_data: dict) -> tuple[int, int]:
    total = 0
    completed = 0

    for module in plan_data.values():
        for plan in module.get("plans", []):
            total += 1
            if plan.get("migration_status") == "completed":
                completed += 1

    return total, completed

def generate_migration_summary(migration_dir: Path) -> dict:
    """Generate migration summary using Knowledge Graph + Migration Plan (no target)."""

    summary = {"source": {}, "migration": {}}

    kg_file = migration_dir / "knowledge_graph.json"
    plan_file = migration_dir / "migration_plan.json"

    # ─────────────────────────────────────────────────────────────
    # SOURCE → FULL Knowledge Graph (DB primary, file fallback)
    # ─────────────────────────────────────────────────────────────
    kg_data = None
    _mig_name = migration_name_ctx.get("")
    if _mig_name:
        try:
            kg_data = _fetch_artifact(_mig_name, ArtifactType.KNOWLEDGE_GRAPH)
        except Exception as e:
            logger.warning(f"Failed to fetch knowledge_graph from DB: {e}")
    if kg_data is None and kg_file.exists():
        try:
            kg_data = read_json_file(str(kg_file))
        except Exception as e:
            logger.warning(f"Failed to read knowledge graph: {e}")
    summary["source"] = kg_data if kg_data else {"analyzed": False}

    # ─────────────────────────────────────────────────────────────
    # MIGRATION → from Migration Plan (DB primary, file fallback)
    # ─────────────────────────────────────────────────────────────
    total = 0
    completed = 0

    plan_data = None
    if _mig_name:
        try:
            plan_data = _fetch_artifact(_mig_name, ArtifactType.MIGRATION_PLAN)
        except Exception as e:
            logger.warning(f"Failed to fetch migration_plan from DB: {e}")
    if plan_data is None and plan_file.exists():
        try:
            plan_data = read_json_file(str(plan_file))
        except Exception as e:
            logger.warning(f"Failed to compute migration completion: {e}")
    if plan_data:
        try:
            total, completed = _compute_plan_completion(plan_data)
        except Exception as e:
            logger.warning(f"Failed to compute migration completion: {e}")

    # derive status cleanly
    if total == 0 or completed == 0:
        status = "not_started"
    elif completed < total:
        status = "in_progress"
    else:
        status = "completed"

    summary["migration"] = {
        "planned": plan_file.exists(),
        "status": status,
        "completed": completed == total and total > 0,
        "progress": {
            "total": total,
            "completed": completed,
            "percentage": (completed / total * 100) if total else 0,
        },
        "kb_built": kg_file.exists(),
    }

    return summary


def _make_json_serializable(obj):
    """Recursively convert objects to JSON-serializable format."""
    if isinstance(obj, dict):
        return {k: _make_json_serializable(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [_make_json_serializable(item) for item in obj]
    elif isinstance(obj, Path):
        return str(obj)
    elif hasattr(obj, "__dict__") and not isinstance(obj, (type,)):
        return str(obj)  
        # Convert class instances to dict
        logger.warning(SC.CLASS_INSTANCE_TO_DICT_WARNING.format(type=type(obj)))
        return _make_json_serializable(obj.__dict__)
    elif isinstance(obj, (str, int, float, bool, type(None))):
        return obj
    else:
        # Fallback: convert to string
        logger.warning(SC.TYPE_TO_STRING_WARNING.format(type=type(obj)))
        return str(obj)

def _detect_configuration_files(source_path: Path) -> List[str]:
    """Detect configuration files in the project."""
    config_extensions = {".env", ".yaml", ".yml", ".ini", ".toml", ".conf"}
    config_files_list = []
    for file_path in source_path.rglob("*"):
        if file_path.is_file():
            if (
                file_path.suffix in config_extensions
                or "config" in file_path.name.lower()
            ):
                if file_path.name != ".gitignore":
                    config_files_list.append(str(file_path.relative_to(source_path)))
    return list(set(config_files_list))


def _parse_semantic_ir_batch_response(response, batch_num: int) -> List[Dict]:
    """Parse LLM response for semantic IR batch."""
    try:
        response_text = getattr(response, "content", str(response)).strip()

        if "```" in response_text:
            response_text = (
                response_text.replace("```json", "").replace("```", "").strip()
            )

        cleaned = response_text.strip()

        start = cleaned.find("[")
        if start == -1:
            logger.warning(SC.BATCH_NO_JSON_ARRAY.format(batch_num=batch_num))
            return []

        end = cleaned.rfind("]")
        if end <= start:
            logger.warning(SC.BATCH_NO_CLOSING_BRACKET.format(batch_num=batch_num))
            return []

        json_text = cleaned[start : end + 1]

        batch_results = json.loads(json_text)

        if isinstance(batch_results, list):
            logger.info(
                SC.BATCH_SEMANTIC_ENTRIES_EXTRACTED.format(
                    batch_num=batch_num, count=len(batch_results)
                )
            )
            return batch_results
        else:
            logger.warning(
                SC.BATCH_EXPECTED_LIST_WARNING.format(
                    batch_num=batch_num, type=type(batch_results)
                )
            )
            return []

    except json.JSONDecodeError as e:
        logger.error(SC.BATCH_JSON_PARSE_ERROR.format(batch_num=batch_num, error=e))
        return []
    except Exception as e:
        logger.error(SC.BATCH_PROCESSING_FAILED.format(batch_num=batch_num, error=e))
        return []


def _process_semantic_ir_batches(
    all_items: List[Dict], language: str, batch_size: int = 100, base_path: Path = None
) -> List[Dict]:
    """
    Process symbol role+summary annotation in batches.
    Single LLM hit per batch — returns [{index, role, summary}] aligned to input order.
    """
    semantic_ir = []
    total_batches = (len(all_items) + batch_size - 1) // batch_size

    logger.info(
        SC.PROCESSING_TOTAL_BATCHES.format(
            total_batches=total_batches, batch_size=batch_size
        )
    )

    for i in range(0, len(all_items), batch_size):
        batch_num = (i // batch_size) + 1
        batch = all_items[i : i + batch_size]

        logger.info(
            SC.PROCESSING_BATCH_ITEMS.format(
                batch_num=batch_num, total_batches=total_batches, items=len(batch)
            )
        )

        # Lean input: strip everything the LLM doesn't need for role/summary
        lean_batch = [
            {
                "index": idx,
                "type":   item.get("type", ""),
                "name":   item.get("name", ""),
                "calls":  item.get("calls", []),
                "params": item.get("parameters", []),
                "methods": [
                    {"name": m.get("name", ""), "calls": m.get("calls", [])}
                    for m in item.get("methods", [])
                ],
            }
            for idx, item in enumerate(batch)
        ]

        prompt = (
            f"Analyze the below context:"
            f"{language}"
            f"INPUT (batch {batch_num}/{total_batches}):\n"
            f"{json.dumps(lean_batch, indent=2)}\n\n"
            f"OUTPUT: a JSON array, one object per input item, in the same order:\n"
            f'[{{"index": 0, "role": "...", "summary": "..."}}, ...]\n'
          
        )

        try:
            original_instructions = getattr(utility_agent, "instructions", None)
            try:
                utility_agent.instructions = dedent(
                    f"""
                    You are a code analysis expert for {language} projects.
                    Your only task: assign a functional role label and a one-sentence summary
                    to each symbol.
                    For each symbol below assign:
                      - role   : <3-5 word functional responsibility phrase>
                      - summary: <one sentence describing responsibility>
                    Rules:
                    - Exactly one entry per input item, preserving index.
                    - Focus on the dominant functional responsibility.
                    - summary must be plain prose, no bullet points.
                    - Output ONLY the JSON array, no markdown fences, no extra text.
                    """
                )
                utility_agent.output_schema = None
                response = utility_agent.run(input=prompt)
                track_tokens(response, source="scanner:semantic_ir_batch")
            finally:
                if original_instructions is not None:
                    utility_agent.instructions = original_instructions

            batch_results = _parse_semantic_ir_batch_response(response, batch_num)

            # Align results back to original batch items by index
            index_map = {r.get("index", idx): r for idx, r in enumerate(batch_results)}
            for idx, item in enumerate(batch):
                result = index_map.get(idx, {})
                semantic_ir.append({
                    # Keep fields _build_semantic_ir_from_project_graph back-annotates from
                    "role":     result.get("role", ""),
                    "summary":  result.get("summary", ""),
                })

        except Exception as e:
            logger.error(SC.BATCH_FAILED.format(batch_num=batch_num, error=e))
            # Pad with empty entries so back-annotation indices stay aligned
            for item in batch:
                semantic_ir.append({
                    "role": "", "summary": "",
                })

    return semantic_ir

def get_non_convertible_files(source_path: Path) -> set:
    """
    Fast rule-based filtering and LLM as fallback.
    """
    logger.info(SC.DETECTING_NON_CONVERTIBLE_FILES)
    try:
        all_files = [
            f.relative_to(source_path) for f in source_path.rglob("*") if f.is_file()
        ]
    except Exception as e:
        logger.error(SC.ERROR_LISTING_FILES.format(error=e))
        return set()
    if not all_files:
        logger.info(SC.NO_FILES_FOUND)
        return set()
    
    try:
        # Apply rule-based exclusions
        excluded, remaining_files = _apply_rule_based_exclusions(all_files, source_path)
        logger.info(SC.RUNNING_RULE_BASED_ANALYSIS.format(file_count=len(remaining_files)))
    except:
        # Apply LLM exclusions
        logger.warning(SC.RULE_BASED_ANALYSIS_FAILED)
        raise

    if not remaining_files:
        logger.info(SC.ALL_FILES_FILTERED_BY_RULES)
        return excluded

    # FINAL SUMMARY
    logger.info(SC.TOTAL_EXCLUDED_FILES.format(count=len(excluded)))

    if excluded:
        samples = sorted(list(excluded))
        logger.info(SC.SAMPLE_EXCLUDED_FILES)
        for sample in samples:
            logger.info(SC.SAMPLE_EXCLUDED_FILE_ITEM.format(file=sample))

    return excluded

EXPECTED_KEYS = {
    "framework": "",
    "framework_version": "",
    "build_tool": "No build tool",
    "libraries": [],
    "databaseName": "NoDatabase",
    "architecture": "Unknown",
    "entityDetected": ["No Entity Detected"],
}


def parse_tech_stack_response(response) -> dict:
    """
    Custom parser for tech stack LLM response.
    Handles:
    - Extra text / markdown
    - Partial/malformed JSON
    - Missing keys
    - Wrong data types
    """

    if not response:
        raise ValueError("Empty LLM response")

    # Extract text safely
    if hasattr(response, "content"):
        text = response.content
    else:
        text = str(response)

    # 🔹 Step 1: Extract JSON block
    # Find the FIRST complete balanced JSON object, not just first { to last }
    brace_depth = 0
    start_idx = None
    json_str = None

    for i, ch in enumerate(text):
        if ch == '{':
            if brace_depth == 0:
                start_idx = i
            brace_depth += 1
        elif ch == '}':
            brace_depth -= 1
            if brace_depth == 0 and start_idx is not None:
                json_str = text[start_idx:i + 1]
                break

    if not json_str:
        logger.error("No JSON found in response")
        return EXPECTED_KEYS.copy()

    # 🔹 Step 2: Try parsing JSON
    try:
        data = json.loads(json_str)
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode failed: {e}")
        return EXPECTED_KEYS.copy()

    # 🔹 Step 3: Normalize + enforce schema
    cleaned = {}

    for key, default_value in EXPECTED_KEYS.items():
        value = data.get(key, default_value)

        # --- Type fixes ---
        if key in ["libraries", "entityDetected"]:
            if not isinstance(value, list):
                value = [str(value)] if value else default_value
        else:
            if not isinstance(value, str):
                value = str(value) if value else default_value

        # --- Empty handling ---
        if value in [None, "", [], {}]:
            value = default_value

        cleaned[key] = value

    # 🔹 Step 4: Extra normalization (optional intelligence)
    cleaned["framework"] = cleaned["framework"].lower()
    cleaned["build_tool"] = cleaned["build_tool"].lower()

    logger.info(f"Parsed Tech Stack: {cleaned}")

    return cleaned

# Known code extensions that must ALWAYS win over SourceAnalyzer hint
_EXTENSION_ALWAYS_WINS = {
    "py", "js", "ts", "jsx", "tsx", "java", "kt", "rb",
    "pl", "pm", "t",   # ← Perl — t is test file, always Perl
    "go", "rs", "cpp", "c", "h", "hpp", "cs", "swift",
    "scala", "ex", "exs", "erl", "hs", "lua", "r", "jl",
    "php", "dart", "groovy", "sh", "bash", "ps1",
}

def detect_source_language(
    file_path: str, source_analyzer_data: Dict[str, Any] = None
) -> str:
    try:
        file_name = Path(file_path).name.lower()
        ext = Path(file_path).suffix.lower().lstrip(".")

        # Step 1: Extension check FIRST for known code extensions
        # — prevents SourceAnalyzer project-level language from overriding
        #   a file's own clearly-known extension (e.g. .t is always Perl)
        if ext in _EXTENSION_ALWAYS_WINS:
            mapped = _map_language_to_ts_identifier(ext)
            if mapped:
                logger.debug(f"Language via extension (priority): {file_path} → {mapped}")
                return mapped

        # Step 2: Exact filename match (e.g. Makefile, Dockerfile)
        mapped = filename_map.get(file_name)
        if mapped:
            logger.debug(f"Language via filename map: {file_path} → {mapped}")
            return mapped

        # Step 3: SourceAnalyzer hint (only for unknown extensions)
        if source_analyzer_data:
            sa_lang = source_analyzer_data.get("primary_language")
            if sa_lang:
                mapped = _map_language_to_ts_identifier(sa_lang)
                if mapped:
                    logger.debug(f"Language via SourceAnalyzer: {file_path} → {mapped}")
                    return mapped

        # Step 4: Extension map for remaining extensions
        if ext:
            mapped = _map_language_to_ts_identifier(ext)
            if mapped:
                logger.debug(f"Language via extension: {file_path} → {mapped}")
                return mapped

        logger.debug(f"Language detection failed for {file_path}, returning unknown")
        return "unknown"

    except Exception as e:
        logger.debug(f"Language detection failed for {file_path}: {e}")
        return "unknown"


def _collect_config_file_contents(
    source_path: Path,
) -> Dict[str, str]:
    """
    Collect configuration file contents for database detection.
    """
    config_content = {}
    config_patterns = ["config", ".env", "database", "settings", "application"]

    # Use rglob for better performance
    config_files = [
        f
        for f in source_path.rglob("*")
        if f.is_file() and any(pattern in f.name.lower() for pattern in config_patterns)
    ]

    for file_path in config_files:
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
                config_content[str(file_path.relative_to(source_path))] = content
                logger.debug(f"Collected {file_path.name} ({len(content)} chars)")

        except Exception as e:
            logger.debug(f"Could not read {file_path.name}: {e}")
            continue

    logger.info(f"Collected {len(config_content)} config files")
    return config_content

def _collect_folder_structure(
    source_path: Path, max_depth: int = 10
) -> tuple[List[str], Dict[str, int]]:
    """
    Collect folder structure and file type counts.
    Language-agnostic directory traversal.
    """
    folder_list = []
    file_types = {}

    logger.info(f"Scanning folder structure: {source_path} (max_depth={max_depth})")

    try:
        skip_dirs = {
            "node_modules", "__pycache__", ".git", "venv", "vendor",
            "target", "build", "dist", ".next", "out", "bin", "obj",
            ".idea", ".vscode", "coverage", ".pytest_cache",
        }

        for root, dirs, files in os.walk(source_path):
            depth = len(Path(root).relative_to(source_path).parts)

            if depth > max_depth:
                logger.debug(f"Max depth exceeded, skipping: {root}")
                dirs[:] = []
                continue

            dirs[:] = [d for d in dirs if d not in skip_dirs and not d.startswith('.')]

            rel_path = str(Path(root).relative_to(source_path))
            if rel_path != ".":
                folder_list.append(rel_path)
                logger.debug(f"Folder: {rel_path}")

            for file in files:
                if file.startswith('.'):
                    logger.debug(f"Skipping hidden file: {file}")
                    continue
                ext = Path(file).suffix.lower()
                if ext:
                    file_types[ext] = file_types.get(ext, 0) + 1

        logger.info(f"Folder scan complete — {len(folder_list)} folders, {len(file_types)} ext types")
        return (folder_list, file_types)

    except Exception as e:
        logger.error(f"Error collecting folder structure: {e}")
        return ([], {})


def _collect_file_paths(source_path: Path, max_depth: int = 10) -> List[str]:
    """
    Collect a list of absolute file paths for all files in the directory tree,
    skipping known non-code directories and hidden files/directories.

    Args:
        source_path: Root path to scan
        max_depth: Maximum directory depth

    Returns:
        List of absolute file paths (as strings)
    """
    file_paths: List[str] = []

    try:
        # Reuse the same skip directories as _collect_folder_structure
        skip_dirs = {
            "node_modules",
            "__pycache__",
            ".git",
            "venv",
            "vendor",
            "target",
            "build",
            "dist",
            ".next",
            "out",
            "bin",
            "obj",
            ".idea",
            ".vscode",
            "coverage",
            ".pytest_cache",
        }

        for root, dirs, files in os.walk(source_path):
            # Calculate depth
            depth = len(Path(root).relative_to(source_path).parts)
            if depth > max_depth:
                # Stop recursing deeper
                dirs[:] = []
                continue

            # Filter out skip directories
            dirs[:] = [d for d in dirs if d not in skip_dirs and not d.startswith(".")]

            for file in files:
                # Skip hidden files
                if file.startswith("."):
                    continue

                file_path = Path(root) / file
                try:
                    file_paths.append(str(file_path.resolve()))
                except Exception:
                    file_paths.append(str(file_path))

        return file_paths
    except Exception as e:
        logger.error(f"Error collecting file paths: {e}")
        return []


def _get_root_files(source_path: Path) -> List[str]:
    """Get list of files in root directory."""
    root_files = []
    try:
        for item in source_path.iterdir():
            if item.is_file():
                root_files.append(item.name)
    except Exception as e:
        logger.error(f"Error listing root files: {e}")

    return root_files

def _analyze_project(source_path: str) -> Dict[str, Any]:
    """Build deterministic project metadata using Specfy Stack Analyser first.

    Stack Analyser is a local, pinned tool in the container. Remote SourceAnalyzer
    remains an optional fallback, never a hard dependency for migration startup.
    """
    try:
        from app.infrastructure.utils.scanner_engine.run_stack_analyser import analyze_stack
        from app.infrastructure.config.settings import settings
        migration_dir = get_migration_directory("", "")
        stack_enabled = os.getenv("STACK_ANALYZER_ENABLED", "true").strip().lower() in {"1", "true", "yes", "on"}
        if stack_enabled:
            stack = analyze_stack(source_path, str(migration_dir))
            if stack.get("success"):
                languages = stack.get("languages") or []
                primary = max(languages, key=lambda x: x.get("lines", 0)).get("name") if languages else None
                info = {
                    "primary_language": primary,
                    "languages": languages,
                    "dependencies": stack.get("dependencies", []),
                    "extensions": [],
                    "technologies": stack.get("technologies", []),
                    "stack_analyzer": {
                        "name": "@specfy/stack-analyser",
                        "version": os.getenv("STACK_ANALYZER_VERSION", "1.27.6"),
                        "children": stack.get("children", []),
                    },
                }
                logger.info("Stack Analyser detected primary=%s, technologies=%d, dependencies=%d", primary, len(info["technologies"]), len(info["dependencies"]))
                return info
            logger.warning("Local Stack Analyser unavailable: %s", stack.get("error"))

        # Optional legacy HTTP analyzer fallback.
        if (settings.analyzer_api_url or "").strip():
            source_analyzer_repo = SourceAnalyzerRepo()
            scan_result = source_analyzer_repo.analyze_source_project(source_path)
            if scan_result and "data" in scan_result:
                return scan_result["data"].get("source_project_info", {}) or {}
    except Exception as e:
        logger.warning("Stack/Source Analyzer unavailable; using local static fallbacks: %s", e)

    return {"primary_language": None, "languages": [], "dependencies": [], "extensions": [], "technologies": []}


def _get_or_create_non_convertible_files(
    migration_dir: Path, source_path_obj: Path, is_target_scan: bool = False
) -> set:
    """Load non-convertible files from consolidated scanner output JSON."""
    # DB primary
    _mig = migration_name_ctx.get("")
    if _mig:
        try:
            _kg = _fetch_artifact(_mig, ArtifactType.KNOWLEDGE_GRAPH)
            if _kg:
                cached = _kg.get("non_convertible_files", [])
                if cached:
                    logger.info("Loaded cached non-convertible files from DB artifact store")
                    return set(cached)
        except Exception as e:
            logger.warning(f"Error reading non_convertible_files from DB: {e}")

    # File fallback
    scanner_file = migration_dir / "knowledge_graph.json"
    if scanner_file.exists():
        try:
            data = read_json_file(str(scanner_file))
            cached = data.get("non_convertible_files", [])
            if cached:
                logger.info("Loaded cached non-convertible files from knowledge_graph.json")
                return set(cached)
        except Exception as e:
            logger.warning(f"Error reading non_convertible_files from scanner output: {e}")
    non_convertible = set(get_non_convertible_files(source_path_obj))
    logger.info(
        f"{'target' if is_target_scan else 'source'} non_convertible_files generated"
    )
    return non_convertible

def _cache_matches_source(cached_graph: dict, source_path: Path) -> bool:
    source_str = str(source_path.resolve())
    return any(source_str in str(k) for k in cached_graph.keys())

def enrich_project_graph(
    symbols: List[dict],
    definition_tags: List[dict],
    call_tags: List[dict],
    import_tags: List[dict],
    file_paths: List[str],
    source_root: Optional[Path],
    language: str,
) -> Tuple[
    List[dict],
    List[dict],
    List[dict]
]:
    """
    Main enrichment pipeline.

    Fills:
      - calls
      - dependencies
      - parameters
      - access
      - inheritance
      - perl test symbols
      - imports

    Returns:

    symbols
    symbol_dependencies
    file_dependencies
    """

    logger.info("Starting graph enrichment")


    # ============================================================
    # Fix line ranges
    # ============================================================

    logger.info("patching end lines")

    _patch_end_lines(symbols)

    # ============================================================
    # Language call extraction
    # ============================================================

    logger.info("extracting calls")

    try:

        _enrich_calls_by_language(
            symbols=symbols,
            source_root=source_root,
        )

    except Exception as e:

        logger.warning(
            f"call enrichment failed: {e}"
        )

    # ============================================================
    # Symbol-level enrichments (registry-driven, language-agnostic)
    # ============================================================

    logger.info("running symbol enrichments")
    _enrich_symbols_by_language(symbols)

    # ============================================================
    # Build call dependencies
    # IMPORTANT:
    # use call_tags not definition_tags
    # ============================================================

    logger.info(
        "building call graph"
    )

    symbols, call_dependencies = (
        _build_calls_from_ctags(
            symbols=symbols,
            call_tags=call_tags,
            source_root=source_root,
        )
    )

    # ============================================================
    # inheritance graph
    # ============================================================

    logger.info(
        "building inheritance graph"
    )

    inheritance_dependencies = (
        _build_inheritance_deps(
            symbols=symbols,
            definition_tags=definition_tags,
            source_root=source_root,
        )
    )

    # ============================================================
    # file dependencies
    # ============================================================

    logger.info(
        "building import graph"
    )

    file_dependencies = []

    seen = set()

    for tag in import_tags:

        try:

            dep = _import_tag_to_dep(
                tag=tag,
                source_root=source_root
            )

            if not dep:
                continue

            key = (
                tag.get("path"),
                dep["name"]
            )

            if key in seen:
                continue

            seen.add(key)

            file_dependencies.append({

                "source":
                tag.get("path"),

                "target":
                dep["name"],

                "type":
                dep["type"],

                "alias":
                dep["alias"]

            })

        except Exception as e:

            logger.warning(
                f"import parse failed: {e}"
            )

    # ============================================================
    # File-level import enrichment (registry-driven, language-agnostic)
    # ============================================================

    # File-level import enrichment (registry-driven, language-agnostic)
    # Reuses the same `seen` set as the ctags import loop above to prevent
    # duplicates when both ctags and the enricher cover the same import.
    logger.info("extracting file-level imports")
    for dep in _enrich_file_deps_by_language(file_paths, language, source_root):
        key = (dep["source"], dep["target"])
        if key not in seen:
            seen.add(key)
            file_dependencies.append(dep)

    # ============================================================
    # attach dependencies onto symbols
    # ============================================================

    logger.info(
        "attaching dependencies"
    )

    dependency_map = defaultdict(list)

    all_dependencies = (
        call_dependencies
        +
        inheritance_dependencies
    )

    for dep in all_dependencies:

        dependency_map[
            dep["source"]
        ].append(dep)

    for sym in symbols:

        sym["dependencies"] = (
            dependency_map.get(
                sym["symbol_id"],
                []
            )
        )

    logger.info(
        f"symbols={len(symbols)} "
        f"deps={len(all_dependencies)} "
        f"filedeps={len(file_dependencies)}"
    )

    return (
        symbols,
        all_dependencies,
        file_dependencies,
    )

def _slugify(name: str) -> str:
    """Convert a display name to a safe symbol_id fragment."""
    return re.sub(r"[^a-zA-Z0-9_]", "_", name).strip("_")[:40]


def _parse_t_file(filepath: str) -> dict:
    """Parse a single .t file and return its Section → Group → Test hierarchy."""
    RE_SECTION          = re.compile(r'''^\s*\$suite->section\(\s*(['"])(.*?)\1\s*\)''')
    RE_GROUP            = re.compile(r'''^\s*\$suite->group\(\s*(['"])(.*?)\1\s*\)''')
    RE_TEST             = re.compile(r'''^\s*\$suite->test\(\s*(['"])(.*?)\1\s*\)''')
    RE_SECTION_SETUP    = re.compile(r'\$suite->section_setup\(')
    RE_SECTION_TEARDOWN = re.compile(r'\$suite->section_teardown\(')
    RE_GROUP_SETUP      = re.compile(r'\$suite->group_setup\(')
    RE_GROUP_TEARDOWN   = re.compile(r'\$suite->group_teardown\(')
    RE_SUITE_SETUP      = re.compile(r'\$suite->suite_setup\(')
    RE_SUITE_TEARDOWN   = re.compile(r'\$suite->suite_teardown\(')
    RE_ASSERTION        = re.compile(
        r'\$suite->(test_ok|gui_ok|cli_ok|test_not_ok|gui_not_ok|gui_equals_ok)\('
    )
    RE_COMMENT = re.compile(r'^\s*#')

    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
    except Exception as e:
        return {
            "file": filepath, "error": str(e), "lines": 0,
            "sections": [], "has_suite_setup": False, "has_suite_teardown": False,
        }

    result = {
        "file":               filepath,
        "lines":              len(lines),
        "has_suite_setup":    False,
        "has_suite_teardown": False,
        "sections":           [],
    }
    current_section = None
    current_group   = None

    for i, line in enumerate(lines, start=1):
        if RE_COMMENT.match(line):
            continue

        if RE_SUITE_SETUP.search(line):    result["has_suite_setup"]    = True
        if RE_SUITE_TEARDOWN.search(line): result["has_suite_teardown"] = True

        m = RE_SECTION.match(line)
        if m:
            current_section = {
                "name": m.group(2), "line": i,
                "has_setup": False, "has_teardown": False, "groups": [],
            }
            result["sections"].append(current_section)
            current_group = None
            continue

        if current_section:
            if RE_SECTION_SETUP.search(line):    current_section["has_setup"]    = True
            if RE_SECTION_TEARDOWN.search(line): current_section["has_teardown"] = True

        m = RE_GROUP.match(line)
        if m:
            current_group = {
                "name": m.group(2), "line": i,
                "has_setup": False, "has_teardown": False, "tests": [],
            }
            if current_section is None:
                current_section = {
                    "name": "__implicit__", "line": 0,
                    "has_setup": False, "has_teardown": False,
                    "groups": [current_group],
                }
                result["sections"].append(current_section)
            else:
                current_section["groups"].append(current_group)
            continue

        if current_group:
            if RE_GROUP_SETUP.search(line):    current_group["has_setup"]    = True
            if RE_GROUP_TEARDOWN.search(line): current_group["has_teardown"] = True

        m = RE_TEST.match(line)
        if m:
            test_entry = {"name": m.group(2), "line": i, "assertion_type": None}
            if current_group is not None:
                current_group["tests"].append(test_entry)
            elif current_section is not None:
                current_group = {
                    "name": "__implicit__", "line": 0,
                    "has_setup": False, "has_teardown": False, "tests": [test_entry],
                }
                current_section["groups"].append(current_group)
            else:
                current_section = {
                    "name": "__implicit__", "line": 0,
                    "has_setup": False, "has_teardown": False, "groups": [],
                }
                current_group = {
                    "name": "__implicit__", "line": 0,
                    "has_setup": False, "has_teardown": False, "tests": [test_entry],
                }
                current_section["groups"].append(current_group)
                result["sections"].append(current_section)
            continue

        m_assert = RE_ASSERTION.search(line)
        if m_assert and current_group and current_group["tests"]:
            last = current_group["tests"][-1]
            if last["assertion_type"] is None:
                last["assertion_type"] = m_assert.group(1)

    return result

def _compute_test_hierarchy_stats(suites: list) -> dict:
    """
    Compute hierarchy statistics and derive adaptive thresholds.

    Uses:
      large samples -> mean + 2σ
      small samples -> median-based estimate

    Derives counts from child objects if count fields are missing.
    """

    tests_per_group = []
    groups_per_section = []

    for s in suites:

        for sec in s.get("sections", []):

            # derive group count if missing
            groups = sec.get("groups", [])
            gc = sec.get("group_count")

            if gc is None:
                gc = len(groups)

            if gc > 0:
                groups_per_section.append(gc)

            for grp in groups:

                # derive test count if missing
                tests = grp.get("tests", [])
                tc = grp.get("test_count")

                if tc is None:
                    tc = len(tests)

                if tc > 0:
                    tests_per_group.append(tc)

    def _stats(data: list, label: str):

        data = [x for x in data if x > 0]

        if not data:
            return {
                "label": label,
                "count": 0,
                "min": 0,
                "mean": 0.0,
                "median": 0.0,
                "max": 0,
                "std": 0.0
            }

        std = round(_stdev(data), 2) if len(data) > 1 else 0.0

        return {
            "label": label,
            "count": len(data),
            "min": min(data),
            "mean": round(_mean(data), 1),
            "median": round(_median(data), 1),
            "max": max(data),
            "std": std
        }

    grp_stats = _stats(
        groups_per_section,
        "groups_per_section"
    )

    tst_stats = _stats(
        tests_per_group,
        "tests_per_group"
    )

    sample_count = tst_stats["count"]

    # small sample => median
    if sample_count < 15:

        group_threshold = max(
            4,
            min(
                12,
                round(grp_stats["median"] * 2)
            )
        )

        test_threshold = max(
            8,
            min(
                25,
                round(tst_stats["median"] * 3)
            )
        )

    else:

        group_threshold = max(
            4,
            min(
                12,
                round(
                    grp_stats["mean"] +
                    2 * grp_stats["std"]
                )
            )
        )

        test_threshold = max(
            8,
            min(
                25,
                round(
                    tst_stats["mean"] +
                    2 * tst_stats["std"]
                )
            )
        )

    test_batch_size = max(
        4,
        min(
            round(test_threshold / 2),
            round(tst_stats["mean"])
        )
    )

    return {

        "total_files": len(suites),

        "sections": _stats(
            [s.get("section_count", len(s.get("sections", [])))
             for s in suites],
            "sections_per_file"
        ),

        "groups": _stats(
            [s.get("group_count",
                   sum(len(sec.get("groups", []))
                   for sec in s.get("sections", [])))
             for s in suites],
            "groups_per_file"
        ),

        "tests": _stats(
            [s.get("test_count",
                   sum(
                       len(g.get("tests", []))
                       for sec in s.get("sections", [])
                       for g in sec.get("groups", [])
                   ))
             for s in suites],
            "tests_per_file"
        ),

        "tests_per_group": tst_stats,
        "groups_per_section": grp_stats,

        "suggested_thresholds": {
            "group_threshold": group_threshold,
            "test_threshold": test_threshold,
            "test_batch_size": test_batch_size
        }
    }

def _assign_line_ranges(suite: dict) -> dict:
    """Post-processing: compute end lines for sections, groups, and tests."""
    total    = suite.get("lines", 0)
    sections = suite.get("sections", [])

    for s_idx, section in enumerate(sections):
        section_end = (
            sections[s_idx + 1]["line"] - 1
            if s_idx + 1 < len(sections)
            else total
        )
        if section["line"] > 0:
            section["line_range"] = {"start": section["line"], "end": section_end}

        groups = section.get("groups", [])
        for g_idx, group in enumerate(groups):
            group_end = (
                groups[g_idx + 1]["line"] - 1
                if g_idx + 1 < len(groups)
                else section_end
            )
            if group["line"] > 0:
                group["line_range"] = {"start": group["line"], "end": group_end}

            tests = group.get("tests", [])
            for t_idx, test in enumerate(tests):
                test_end = (
                    tests[t_idx + 1]["line"] - 1
                    if t_idx + 1 < len(tests)
                    else group_end
                )
                test["line_range"] = {"start": test["line"], "end": test_end}

    return suite

def _generate_or_load_project_graph(
    migration_dir: Path,
    source_path_obj: Path,
    non_convertible: set,
    primary_language: str,
    is_target_scan: bool = False,
) -> dict:
    """Single source of truth for AST + graph loading/generation."""
    source_str = str(source_path_obj.resolve())

    def _validate_and_return(data: dict):
        cached_graph = data.get("project_graph", {})
        cached_files = cached_graph.get("files", [])
        cache_valid = any(source_str in str(f.get("file_path", "")) for f in cached_files)
        return cached_graph if (cached_graph and cache_valid) else None

    # DB primary
    _mig = migration_name_ctx.get("")
    if _mig:
        try:
            _kg = _fetch_artifact(_mig, ArtifactType.KNOWLEDGE_GRAPH)
            if _kg:
                result = _validate_and_return(_kg)
                if result is not None:
                    logger.info("✅ Loaded cached project_graph from DB artifact store")
                    return result
        except Exception as e:
            logger.warning(f"Cache read from DB failed: {e}")

    # File fallback
    scanner_file = migration_dir / "knowledge_graph.json"
    if scanner_file.exists():
        try:
            data = read_json_file(str(scanner_file))
            result = _validate_and_return(data)
            if result is not None:
                logger.info("✅ Loaded cached project_graph from knowledge_graph.json")
                return result
        except Exception as e:
            logger.warning(f"Cache read failed: {e}")

    logger.info(f"Generating fresh AST for {'target' if is_target_scan else 'source'}...")
    convertible_files = _collect_convertible_files(source_path_obj, non_convertible)
    file_paths = _collect_file_paths(source_path_obj)

    project_graph= _parse_convertible_files(
        convertible_files=convertible_files,
        detected_primary_language=primary_language,
        file_paths=file_paths,
        source_root=source_path_obj,
    )

    return project_graph

def _parse_convertible_files(
    convertible_files: List[Path],
    detected_primary_language: str,
    file_paths: Optional[List[str]] = None,
    source_root: Optional[Path] = None,
) -> dict:
    """
    Unified parser:
      - .t / .test files  → hierarchy parser (preamble/section/group/test/teardown)
      - all other files   → ctags pipeline
    Dependencies always emitted as flat {source, target, type, alias} dicts.
    """
    project_graph: dict = {
        "files":               [],
        "symbols":             [],
        "symbol_dependencies": [],
        "dependencies":        [],
        "file_index":          {},
    }

    if not convertible_files:
        return project_graph

    # ── Route files by type ───────────────────────────────────────────────────
#-------------------------------------------------------------------------------
#Area of improvement: if we want to support more test file patterns in the future, we could make the test file detection more flexible, e.g. by using a regex or a configurable list of patterns instead of hardcoding .t and .test extensions.
    t_files      = [f for f in convertible_files if f.suffix.lower() in {".t", ".test"}]
    regular_files = [f for f in convertible_files if f.suffix.lower() not in {".t", ".test"}]
#-------------------------------------------------------------------------------
    all_symbols:   List[dict] = []
    all_sym_deps:  List[dict] = []
    all_file_deps: List[dict] = []

    # =========================================================================
    # .t / .test  —  hierarchy parser
    # =========================================================================

    parsed_suites: List[dict] = []   

    for file_path in t_files:

        file_path_str = str(file_path.resolve())
        file_stem     = file_path.stem

        try:
            language = detect_source_language(
                file_path_str,
                source_analyzer_data={"primary_language": detected_primary_language},
            )
        except Exception:
            language = ""
        if not language or language.lower() in {"unknown", "none", ""}:
            language = detected_primary_language or "unknown"

        project_graph["files"].append({
            "file_path":  file_path_str,
            "language":   language,
            "complexity": 0.0,
        })

        suite = _parse_t_file(file_path_str)
        suite = _assign_line_ranges(suite)

        # ── add metrics to suite then collect ────────────────────────────
        for sec in suite.get("sections", []):
            sec["group_count"] = len(sec.get("groups", []))
            sec["test_count"]  = sum(
                len(g.get("tests", [])) for g in sec.get("groups", [])
            )
        suite["section_count"] = len(suite.get("sections", []))
        suite["group_count"]   = sum(
            s.get("group_count", 0) for s in suite.get("sections", [])
        )
        suite["test_count"]    = sum(
            s.get("test_count", 0) for s in suite.get("sections", [])
        )
        parsed_suites.append(suite)
        # ─────────────────────────────────────────────────────────────────

        if suite.get("error"):
            logger.warning(f"Skipping {file_path_str}: {suite['error']}")
            continue

        sections    = suite.get("sections", [])
        total_lines = suite.get("lines", 0)
        file_syms:  List[dict] = []
        file_deps:  List[dict] = []

        # ── Preamble ──────────────────────────────────────────────────────────
        if sections and sections[0]["line"] > 1:
            preamble_end = sections[0]["line"] - 1
            pid = _build_symbol_id(source_root, file_path_str, f"{file_stem}_preamble")
            file_syms.append({
                "symbol_id":     pid,
                "symbol_type":   "preamble",
                "name":          f"{file_stem}_setup",
                "language":      language,
                "parent_symbol": None,
                "file_path":     file_path_str,
                "parameters":    [],
                "return_type":   None,
                "access":        None,
                "inherits":      [],
                "ast_node_type": "preamble",
                "calls":         [],
                "dependencies":  [],
                "line_range":    {"start": 1, "end": preamble_end},
                "symbol_hash":   _stable_hash(pid),
                "role":          "preamble",
                "complexity":    0.0,
                "meta": {
                    "has_suite_setup":    suite.get("has_suite_setup",    False),
                    "has_suite_teardown": suite.get("has_suite_teardown", False),
                },
            })

        # ── Section → Group → Test ────────────────────────────────────────────
        for s_idx, section in enumerate(sections):

            sec_name = section["name"]
            sec_id   = _build_symbol_id(
                source_root, file_path_str, f"sec_{s_idx}_{_slugify(sec_name)}"
            )
            file_syms.append({
                "symbol_id":     sec_id,
                "symbol_type":   "section",
                "name":          sec_name,
                "language":      language,
                "parent_symbol": None,
                "file_path":     file_path_str,
                "parameters":    [],
                "return_type":   None,
                "access":        None,
                "inherits":      [],
                "ast_node_type": "section",
                "calls":         [],
                "dependencies":  [],
                "line_range":    section["line_range"],
                "symbol_hash":   _stable_hash(sec_id),
                "role":          "section",
                "complexity":    0.0,
                "meta": {
                    "has_setup":    section.get("has_setup",    False),
                    "has_teardown": section.get("has_teardown", False),
                    "group_count":  len(section.get("groups", [])),
                    "test_count":   sum(
                        len(g.get("tests", [])) for g in section.get("groups", [])
                    ),
                },
            })

            for g_idx, group in enumerate(section.get("groups", [])):

                grp_name = group["name"]
                grp_id   = _build_symbol_id(
                    source_root, file_path_str,
                    f"grp_{s_idx}_{g_idx}_{_slugify(grp_name)}"
                )
                file_syms.append({
                    "symbol_id":     grp_id,
                    "symbol_type":   "group",
                    "name":          grp_name,
                    "language":      language,
                    "parent_symbol": sec_id,
                    "file_path":     file_path_str,
                    "parameters":    [],
                    "return_type":   None,
                    "access":        None,
                    "inherits":      [],
                    "ast_node_type": "group",
                    "calls":         [],
                    "dependencies":  [],
                    "line_range":    group["line_range"],
                    "symbol_hash":   _stable_hash(grp_id),
                    "role":          "group",
                    "complexity":    0.0,
                    "meta": {
                        "has_setup":    group.get("has_setup",    False),
                        "has_teardown": group.get("has_teardown", False),
                        "test_count":   len(group.get("tests",    [])),
                        "section":      sec_name,
                    },
                })
                file_deps.append({
                    "source": sec_id, "target": grp_id, "kind": "contains"
                })

                for t_idx, test in enumerate(group.get("tests", [])):

                    tst_name = test["name"]
                    tst_id   = _build_symbol_id(
                        source_root, file_path_str,
                        f"tst_{s_idx}_{g_idx}_{t_idx}_{_slugify(tst_name)}"
                    )
                    file_syms.append({
                        "symbol_id":     tst_id,
                        "symbol_type":   "test",
                        "name":          tst_name,
                        "language":      language,
                        "parent_symbol": grp_id,
                        "file_path":     file_path_str,
                        "parameters":    [],
                        "return_type":   None,
                        "access":        None,
                        "inherits":      [],
                        "ast_node_type": "test",
                        "calls":         [],
                        "dependencies":  [],
                        "line_range":    test["line_range"],
                        "symbol_hash":   _stable_hash(tst_id),
                        "role":          "test",
                        "complexity":    0.0,
                        "meta": {
                            "assertion_type": test.get("assertion_type"),
                            "section":        sec_name,
                            "group":          grp_name,
                        },
                    })
                    file_deps.append({
                        "source": grp_id, "target": tst_id, "kind": "contains"
                    })

        # ── Teardown ──────────────────────────────────────────────────────────
        if sections:
            last_end = sections[-1].get("line_range", {}).get("end", 0)
            if last_end and last_end < total_lines:
                tid = _build_symbol_id(
                    source_root, file_path_str, f"{file_stem}_teardown"
                )
                file_syms.append({
                    "symbol_id":     tid,
                    "symbol_type":   "teardown",
                    "name":          f"{file_stem}_teardown",
                    "language":      language,
                    "parent_symbol": None,
                    "file_path":     file_path_str,
                    "parameters":    [],
                    "return_type":   None,
                    "access":        None,
                    "inherits":      [],
                    "ast_node_type": "teardown",
                    "calls":         [],
                    "dependencies":  [],
                    "line_range":    {"start": last_end + 1, "end": total_lines},
                    "symbol_hash":   _stable_hash(tid),
                    "role":          "teardown",
                    "complexity":    0.0,
                })

        # ── Enrichments (registry-driven, language-agnostic) ──────────────────
        # Temporarily masquerade hierarchy types as "function" so both
        # symbol and call enrichers recognise them (they filter on symbol_type).
        _T_TYPES = {"section", "group", "test", "preamble", "teardown"}
        for sym in file_syms:
            if sym.get("ast_node_type") in _T_TYPES:
                sym["_orig_type"] = sym["symbol_type"]
                sym["symbol_type"] = "function"

        _enrich_symbols_by_language(file_syms)
        _enrich_calls_by_language(file_syms, source_root)

        for sym in file_syms:
            if "_orig_type" in sym:
                sym["symbol_type"] = sym.pop("_orig_type")

        # ── File-level imports ────────────────────────────────────────────────
        try:
            for dep in _extract_perl_imports(file_path_str, source_root):
                all_file_deps.append({
                    "source": file_path_str,
                    "target": dep["name"],
                    "type":   dep["type"],
                    "alias":  dep["alias"],
                })
        except Exception as e:
            logger.warning(f"perl imports failed {file_path_str}: {e}")

        all_symbols.extend(file_syms)
        all_sym_deps.extend(file_deps)

    # ── Test hierarchy stats (only when .t files were parsed) ────────────────
    if parsed_suites:
        project_graph["test_hierarchy_stats"] = _compute_test_hierarchy_stats(
            parsed_suites
        )

    # =========================================================================
    # REGULAR FILES  —  ctags pipeline
    # =========================================================================

    if regular_files:

        files_payload, name_to_abs = _build_files_payload_relative(
            regular_files, source_root
        )

        if files_payload:

            # ── ctags parse ───────────────────────────────────────────────────
            reg_def_tags: List[dict] = []
            reg_imp_tags: List[dict] = []
            reg_call_tags: List[dict] = []

            try:
                parse_resp = parse(
                    ParseRequest(
                        files=[
                            FilePayload(name=f["name"], content=f["content"])
                            for f in files_payload
                        ]
                    )
                )
                reg_def_tags  = _remap_paths(
                    [dict(t) for t in parse_resp.definition_tags], name_to_abs
                )
                reg_imp_tags  = _remap_paths(
                    [dict(t) for t in parse_resp.import_tags],     name_to_abs
                )
                reg_call_tags = _remap_paths(
                    [dict(t) for t in parse_resp.call_tags],       name_to_abs
                )
                for err in parse_resp.errors:
                    logger.warning(f"ctags: {err}")

            except Exception as e:
                logger.error(f"ctags parse failed: {e}")

            # ── Build symbols from definition tags ────────────────────────────
            defs_by_file: Dict[str, List[dict]] = defaultdict(list)
            for tag in reg_def_tags:
                fp = tag.get("path", "")
                if fp:
                    try:    defs_by_file[str(Path(fp).resolve())].append(tag)
                    except: defs_by_file[fp].append(tag)

            reg_symbols: List[dict] = []

            for file_path in regular_files:

                file_path_str = str(file_path.resolve())

                try:
                    language = detect_source_language(
                        file_path_str,
                        source_analyzer_data={
                            "primary_language": detected_primary_language
                        },
                    )
                except Exception:
                    language = ""
                if not language or language.lower() in {"unknown", "none", ""}:
                    language = detected_primary_language or "unknown"

                project_graph["files"].append({
                    "file_path":  file_path_str,
                    "language":   language,
                    "complexity": 0.0,
                })

                for tag in defs_by_file.get(file_path_str, []):
                    sym = _tag_to_symbol(tag, source_root, language)
                    if sym:
                        reg_symbols.append(sym)

            # ── Enrich via shared pipeline ────────────────────────────────────
            if reg_symbols:
                try:
                    reg_symbols, reg_sym_deps, reg_file_deps = enrich_project_graph(
                        symbols=reg_symbols,
                        definition_tags=reg_def_tags,
                        call_tags=reg_call_tags,
                        import_tags=reg_imp_tags,
                        file_paths=[str(f.resolve()) for f in regular_files],
                        source_root=source_root,
                        language=detected_primary_language,
                    )
                    all_sym_deps.extend(reg_sym_deps)
                    all_file_deps.extend(reg_file_deps)
                except Exception as e:
                    logger.warning(f"graph enrichment failed: {e}")

            all_symbols.extend(reg_symbols)

    # ── Merge and finalise ────────────────────────────────────────────────────
    project_graph["symbols"]             = all_symbols
    project_graph["symbol_dependencies"] = all_sym_deps
    project_graph["dependencies"]        = all_file_deps
    project_graph["file_index"]          = _build_file_index(all_symbols)

    t_count   = sum(1 for s in all_symbols if s.get("ast_node_type") in
                    {"preamble", "section", "group", "test", "teardown"})
    reg_count = len(all_symbols) - t_count

    logger.info(
        f"Scanner complete — "
        f"files: {len(project_graph['files'])} "
        f"({len(t_files)} .t, {len(regular_files)} regular), "
        f"symbols: {len(all_symbols)} "
        f"({t_count} hierarchy, {reg_count} ctags), "
        f"deps: {len(all_file_deps)}, "
        f"symbol_deps: {len(all_sym_deps)}"
    )
    return project_graph

def _detect_tech_stack(
    migration_dir: Path,
    source_path_obj: Path,
    project_graph: dict,
    source_project_info: Dict[str, Any],
    primary_language: str,
    is_target_scan: bool = False,
) -> dict:
    """Single LLM call for complete tech detection (Tech Stack + Architecture + Build Tool)."""
    
    # 1. Cache check — DB primary, file fallback
    _mig = migration_name_ctx.get("")
    if _mig:
        try:
            _kg = _fetch_artifact(_mig, ArtifactType.KNOWLEDGE_GRAPH)
            if _kg:
                cached_tech = _kg.get("tech_data", {})
                if cached_tech.get("architecture") and cached_tech.get("build_tool"):
                    logger.info("✅ Loaded full cached tech_data from DB")
                    return cached_tech
        except Exception as e:
            logger.warning(f"Cache read from DB failed: {e}")

    scanner_file = migration_dir / "knowledge_graph.json"
    if scanner_file.exists():
        try:
            data = read_json_file(str(scanner_file))
            cached_tech = data.get("tech_data", {})
            if cached_tech.get("architecture") and cached_tech.get("build_tool"):
                logger.info("✅ Loaded full cached tech_data from file")
                return cached_tech
        except Exception as e:
            logger.warning(f"Cache read failed: {e}")

    # 2. Collect extra context for LLM
    file_structure, file_types = _collect_folder_structure(source_path_obj, max_depth=8)
    root_files = _get_root_files(source_path_obj)

    # 3. Single LLM call for everything
    llm_tech = _detect_full_tech_stack_with_llm(
        project_graph=project_graph,
        source_path=source_path_obj,
        source_analyzer_data=source_project_info,
        folder_structure=file_structure,
        file_types=file_types,
        root_files=root_files,
    )

    # 4. Build base + merge LLM results
    tech = _build_base_tech_data(source_project_info, project_graph, primary_language)
    tech = _merge_tech_with_llm_results(tech, llm_tech)
    tech = _enrich_tech_statically(tech, project_graph)

    logger.info(
        f"Final Tech Stack → Language: {tech.get('language')} | "
        f"Framework: {tech.get('framework') or 'None'} | "
        f"Architecture: {tech.get('architecture')} | "
        f"Build Tool: {tech.get('build_tool')}"
    )

    return tech

def _detect_full_tech_stack_with_llm(
    project_graph: dict,
    source_path: Path,
    source_analyzer_data: Dict[str, Any] = None,
    folder_structure: List[str] = None,
    file_types: Dict[str, int] = None,
    root_files: List[str] = None,
) -> dict:
    """ONE LLM CALL: Detects everything in a single prompt."""

    config_file_names = _detect_configuration_files(source_path)
    config_contents = _collect_config_file_contents(source_path)

    context_parts = []

    if source_analyzer_data:
        sa_lang = source_analyzer_data.get("primary_language")
        if sa_lang:
            context_parts.append(f"Primary Language: {sa_lang}")

        deps = source_analyzer_data.get("dependencies")
        if deps:
            context_parts.append(f"Dependencies: {json.dumps(deps)}")

    if folder_structure:
        limited_structure = folder_structure
        context_parts.append(
            f"FOLDER STRUCTURE:\n{chr(10).join(limited_structure)}"
        )

    if file_types:
        context_parts.append(f"FILE TYPES: {json.dumps(file_types)}")

    if root_files:
        context_parts.append(f"ROOT FILES: {', '.join(root_files)}")

    if config_contents:
        config_block = "\n\n".join(
            f"### {fname}\n{content}"
            for fname, content in list(config_contents.items())
        )
        context_parts.append(f"CONFIG FILES:\n{config_block}")

    context_block = "\n\n".join(context_parts) or "No metadata available."

    prompt = f"""
Analyze the project and detect the following technical details based on the provided context.

PROJECT CONTEXT:
{context_block}

Return ONLY this JSON structure:
{{
  "framework": "string or empty",
  "framework_version": "string or empty",
  "build_tool": ""string or No build tool",
  "libraries": ["lib1", "lib2", ...],
  "databaseName": ""string or NoDatabase",
  "architecture": ""string or Unknown",
  "entityDetected": ["User", "Order", ...] or ["No Entity Detected"]
}}
"""

    try:
        response = tech_detector.run(input=prompt)
        track_tokens(response, source="scanner:tech_stack_detect")
        result = parse_tech_stack_response(response)
        print(result)
        return result if isinstance(result, dict) else {}

    except Exception as e:
        logger.error(f"Tech stack LLM failed: {e}")
        return {}

def _detect_primary_language(
    source_project_info: Dict, 
    source_path_obj: Path, 
    non_convertible: set
) -> str:
    """Detect primary language with fallback chain."""
    primary = source_project_info.get("primary_language")
    
    convertible_files = _collect_convertible_files(source_path_obj, non_convertible)
    if convertible_files:
        first_file = str(convertible_files[0])
        detected = detect_source_language(first_file, source_project_info)
        if detected and detected.lower() not in {"unknown", "none", ""}:
            return detected 
    mapped = _map_language_to_ts_identifier(primary) if primary else None
    if mapped:
        return mapped

    # Deterministic fallback: project-level analyzer may be unavailable in the
    # container, but the local source tree is authoritative for extension-based
    # language detection. Choose the most common recognized source extension.
    extension_counts: dict[str, int] = {}
    for file_path in convertible_files:
        ext = file_path.suffix.lower().lstrip(".")
        candidate = _map_language_to_ts_identifier(ext) if ext else None
        if candidate:
            extension_counts[candidate] = extension_counts.get(candidate, 0) + 1
    if extension_counts:
        return max(extension_counts, key=extension_counts.get)

    return "unknown"

def _compute_total_loc_from_symbols(project_graph: dict) -> int:
    total_loc = 0

    for sym in project_graph.get("symbols", []):
        line_range = sym.get("line_range") or {}
        start = line_range.get("start")
        end = line_range.get("end")

        if isinstance(start, int) and isinstance(end, int) and end >= start:
            total_loc += (end - start + 1)

    return total_loc

def _build_base_tech_data(
    source_project_info: Dict, 
    project_graph: dict, 
    primary_language: str
) -> dict:
    """Build initial tech dict from static analysis only."""

    total_loc = _compute_total_loc_from_symbols(project_graph)
    target_language = target_language_ctx.get("") #### Placeholder - will be set properly in main flow

    # ── Dependency counts ─────────────────────────────────────────────────
    # Internal: unique inter-symbol dependencies
    internal_deps = {
        (d["source"], d["target"])
        for d in project_graph.get("symbol_dependencies", [])
        if d.get("source") and d.get("target")
    }

    # External: unique third-party/local package names across all files
    external_deps = {
        dep["name"]
        for file_entry in project_graph.get("dependencies", [])
        for dep in file_entry.get("dependencies", [])
        if dep.get("name")
    }

    dependency_counts = {
        "total":    len(internal_deps) + len(external_deps),
        "internal": len(internal_deps),
        "external": len(external_deps),
    }

    return {
        "language": primary_language,
        "languages": source_project_info.get("languages", []),
        "target_language": target_language,  
        "dependencies": source_project_info.get("dependencies", []),
        "extensions": source_project_info.get("extensions", []),
        "total_loc": total_loc, 
        "libraries": [],           # Will be filled later
        "framework": "",
        "framework_version": "",
        "build_tool": "No build tool",
        "databaseName": "NoDatabase",
        "configurationFiles": [],
        "architecture": "Unknown",
        "entityDetected": ["No Entity Detected"],
        "dependency_counts":  dependency_counts,
    }


def _merge_tech_with_llm_results(base_tech: dict, llm_tech: dict) -> dict:
    merged = base_tech.copy()
    
    if llm_tech:
        for key in ["framework", "framework_version", "databaseName", "build_tool", "architecture"]:
            if llm_tech.get(key) and str(llm_tech.get(key)).strip() not in {"", "NoDatabase", "Unknown"}:
                merged[key] = llm_tech[key]
        
        llm_entities = llm_tech.get("entityDetected", [])
        if (
            llm_entities 
            and isinstance(llm_entities, list) 
            and llm_entities != ["No Entity Detected"]
        ):
            merged["entityDetected"] = llm_entities

        # Libraries
        llm_libs = llm_tech.get("libraries", [])
        if llm_libs and isinstance(llm_libs, list):
            merged["libraries"] = [lib for lib in llm_libs if lib]
    
    return merged


def _enrich_tech_statically(tech: dict, project_graph: dict) -> dict:
    """Lightweight static enrichment - only fills gaps."""
    # Add libraries from graph dependencies
    graph_deps = [
        d.get("name", "") for d in project_graph.get("dependencies", [])
        if isinstance(d, dict) and d.get("name")
    ]
    tech["libraries"] = list(set(tech.get("libraries", []) + graph_deps))

    # Add extensions from files if missing
    if not tech.get("extensions"):
        exts = {
    Path(f.get("file_path","")).suffix.lower()
    for f in project_graph.get("files", [])
    if Path(f.get("file_path","")).suffix
}
        tech["extensions"] = list(exts)

    return tech

def compute_ast_complexity(project_graph: dict) -> dict:
    """
    Core AST-based complexity calculation.

    Mutates and returns project_graph with:
      - symbol["complexity"]
      - file["complexity"]
      - modules dict: complexity field updated per module (preserves labels from Step 4)

    Skips symbol/file scoring if all symbols already have complexity set.
    """
    symbols = project_graph.get("symbols", [])
    files = project_graph.get("files", [])

    # Skip if all symbols already scored
    if symbols and all((s.get("complexity") or 0.0) > 0.0 for s in symbols):
        logger.info("Symbol complexity already computed — skipping re-computation")
        return project_graph

    # ---------------------------
    # Step 1 — Symbol complexity
    # ---------------------------
    file_complexity: dict[str, float] = {}
    module_complexity: dict[str, float] = {}

    for symbol in symbols:
        params = symbol.get("parameters") or []
        calls = symbol.get("calls") or []
        deps = symbol.get("dependencies") or []

        parameter_count = len(params)
        call_count = len(calls)
        dependency_count = len(deps)

        LOC = 0.0
        line_range = symbol.get("line_range") or {}
        start = line_range.get("start")
        end = line_range.get("end")
        if isinstance(start, int) and isinstance(end, int):
            LOC = max(0.0, float(end - start))

        LOC_weight = max(1.0, LOC / 10.0)

        complexity = (
            float(parameter_count)
            + float(call_count)
            + float(dependency_count)
            + LOC_weight
        )
        symbol["complexity"] = complexity

        file_path = symbol.get("file_path")
        if file_path:
            file_complexity[file_path] = file_complexity.get(file_path, 0.0) + complexity

        module = symbol.get("module")
        if module:
            module_complexity[module] = module_complexity.get(module, 0.0) + complexity

    # ---------------------------
    # Step 2 — File complexity
    # ---------------------------
    for file_entry in files:
        file_path = file_entry.get("file_path")
        if not file_path:
            continue
        file_entry["complexity"] = file_complexity.get(file_path, 0.0)

    # ---------------------------
    # Step 3 — Module complexity
    # Preserve dict format if Step 4 already labelled modules.
    # Only fall back to list format if no labelled dict exists.
    # ---------------------------
    existing_modules = project_graph.get("modules")
    if isinstance(existing_modules, dict) and existing_modules:
        # Labelled dict from Step 4 — update complexity in-place by matching symbol module paths
        sym_complexity_by_id: dict[str, float] = {
            s.get("symbol_id", ""): s.get("complexity", 0.0) for s in symbols
        }
        for mod_name, mod_data in existing_modules.items():
            mod_data["complexity"] = sum(
                sym_complexity_by_id.get(sid, 0.0)
                for sid in mod_data.get("symbols", [])
            )
        project_graph["modules"] = existing_modules
    else:
        # No labelled modules yet — write flat list as before
        project_graph["modules"] = [
            {"module_path": mod_path, "complexity": cplx}
            for mod_path, cplx in module_complexity.items()
        ]

    return project_graph

def get_folder_structure(root_path: Path) -> list[str]:
    folders = set()

    for p in root_path.rglob("*"):
        if p.is_dir():
            rel = p.relative_to(root_path).as_posix()
            if rel != ".":
                folders.add(rel)

    return sorted(folders)

# ── Helper 1: detect file/module-scope symbols ─────────────────────────────
# Uses structural evidence only — no hardcoded type names.
# A symbol is file-scope if it has zero resolved inbound deps,
# zero resolved outbound deps, AND an empty calls list.
# This catches 'script', 'module', 'file', 'package', 'namespace',
# 'compilation_unit', or whatever name the pipeline uses.

def detect_file_scope_ids(
    symbols: list,
    sym_deps: list,
    sym_id_key: str,
    sym_calls_key: str,
    sym_call_name_key: str,
    dep_resolved_key: str,
    dep_source_key: str,
    dep_target_key: str,
) -> set:
    '''Returns a set of symbol IDs that are likely file/module-scope, based on calls.'''
    has_inbound  = set() # IDs that are targets of resolved deps
    has_outbound = set() # IDs that are sources of resolved deps
    for dep in sym_deps:
        if not dep.get(dep_resolved_key):
            continue
        has_outbound.add(dep.get(dep_source_key))
        has_inbound.add(dep.get(dep_target_key))

    file_scope = set()
    for sym in symbols:
        sid = sym.get(sym_id_key)
        # calls is a list of dicts — symbol is isolated if list is empty
        calls = sym.get(sym_calls_key, []) or []
        has_any_call = any(
            c.get(sym_call_name_key) for c in calls
        ) if calls else False
        if (sid not in has_inbound
                and sid not in has_outbound
                and not has_any_call):
            file_scope.add(sid)
    return file_scope


# ── Helper 2: role domain extractor ───────────────────────────────────────
# Learns which role segments are domain-meaningful from the data itself.
# No hardcoded stopword list.

def build_role_domain_extractor(all_roles: list) -> callable:
    '''Returns a function that extracts the most domain-meaningful segment from a role string.'''
    def split_role(role: str) -> list:
        if not role:
            return []
        parts = re.split(r'[_\-\.]|(?<=[a-z])(?=[A-Z])', role)
        return [p.lower() for p in parts if p]

    n = len(all_roles)
    seg_doc_freq = Counter() # counts how many roles each segment appears in
    for role in all_roles:
        for seg in set(split_role(role)):  # use set to count each segment once per role
            seg_doc_freq[seg] += 1 # each segment counts once per role, not once per occurrence

    # Keep segments that appear in 5–60% of roles:
    # too rare = noise, too common = generic prefix shared by all
    good_segs = {   
        seg for seg, freq in seg_doc_freq.items()
        if n > 0 and 0.05 < (freq / n) < 0.60
    } # set of segments that are neither too rare nor too common

    def extract_role_domain(role: str) -> str:
        parts = split_role(role)
        domain_parts = [p for p in parts if p in good_segs] # filter to only the meaningful segments
        return domain_parts[0] if domain_parts else (parts[0] if parts else "")

    return extract_role_domain


# ── Helper 3: adaptive semantic threshold ──────────────────────────────────
# Calibrates to the similarity distribution of this corpus automatically.

def compute_adaptive_threshold(embeddings: list, percentile: float) -> float:
    if len(embeddings) < 2:
        return 0.60
    sims = [
        float(cosine_similarity([embeddings[i]], [embeddings[j]])[0][0]) # pairwise cosine similarity
        for i in range(len(embeddings))
        for j in range(i + 1, len(embeddings))
    ]
    return float(np.percentile(sims, percentile))


# ── Helper 4: igraph → networkx key lookup ─────────────────────────────────
# igraph.from_networkx stores the nx node ID as '_nx_name'.
# This helper falls back gracefully if the key name ever changes.

def nx_name_from_igraph(iG, ig_idx: int) -> str: # given an igraph vertex index, return the original networkx node name
    v = iG.vs[ig_idx] # get the vertex object for this index
    return v["_nx_name"] if "_nx_name" in v.attributes() else v["name"] # fallback to 'name' if '_nx_name' key is missing

def generate_module_label(
    community_symbols: list,
    cfg: dict,
) -> dict:
    """
    Generate an architectural module label and summary using an LLM.
    Uses a language-agnostic prompt to focus on functional responsibility.
    """

    S = cfg["schema"]

    # -------- Context Construction --------
    context_lines = [
        f"- Symbol: {s.get(S['sym_name'], 'unknown')} | "
        f"Role: {s.get(S['sym_role'], 'N/A')} | "
        f"Info: {s.get(S['sym_summary'], '')}"
        for s in community_symbols
    ]

    context = "\n".join(context_lines)

    original_instructions = getattr(utility_agent, "instructions", None)

    def _to_snake_case(name: str) -> str:
        if not name:
            return name
        name = re.sub(r"[^\w\s]", "", name).strip()
        name = re.sub(r"[\s_]+", "_", name)
        return name.lower()

    def _extract_json(text: str) -> dict | None:
        """Brace-depth balanced JSON extractor."""
        brace_depth = 0
        start_idx = None
        for i, ch in enumerate(text):
            if ch == '{':
                if brace_depth == 0:
                    start_idx = i
                brace_depth += 1
            elif ch == '}':
                brace_depth -= 1
                if brace_depth == 0 and start_idx is not None:
                    try:
                        return json.loads(text[start_idx:i + 1])
                    except json.JSONDecodeError:
                        return None
        return None

    default_res = {
        cfg["label_key_name"]:    "uncategorized_module",
        cfg["label_key_summary"]: "",
        cfg["label_key_role"]:    "",
    }

    try:
        utility_agent.instructions = dedent("""
        You are a senior software architect analyzing clusters of program symbols.
        Your goal is to identify the architectural responsibility of the cluster.

        Rules:
        - Focus on the dominant functional responsibility.
        - Ignore small helper functions when naming the module.
        - Do not use generic names like "Service" or "Management" unless appropriate.
        - Use concise architectural terms (3-5 words): e.g. Book Repository, Student Operations,
          Administrator Management, Application Navigation, Authentication.
        - Output ONLY a valid JSON object. No markdown, no explanation, no preamble.
        """)

        utility_agent.output_schema = None

        response = utility_agent.run(
            f"""Analyze the following symbols and return a module label.
        CONTEXT:
        {context}

        Return ONLY this exact JSON structure with no extra text:
        {{
        "module_name": "concise descriptive name (3-5 words)",
        "role": "functional responsibility phrase (3-5 words)",
        "summary": "one clear sentence explaining the responsibility"
        }}"""
        )
        track_tokens(response, source="scanner:module_label")

        if not response:
            raise ValueError("Empty response from LLM")

        content = (
            response.content if hasattr(response, "content")
            else response.choices[0].message.content if hasattr(response, "choices")
            else str(response)
        ).strip()

        logger.debug(f"generate_module_label raw response: {content!r}")

        res = dict(default_res)  # start from default

        # 1️⃣ Balanced JSON extraction
        parsed = _extract_json(content)
        if parsed and isinstance(parsed, dict):
            raw_name = (
                parsed.get("module_name")
                or parsed.get("name")
                or parsed.get(cfg["label_key_name"])
                or ""
            )
            if raw_name:
                res[cfg["label_key_name"]]    = _to_snake_case(raw_name)
                res[cfg["label_key_summary"]] = parsed.get("summary") or parsed.get(cfg["label_key_summary"]) or ""
                res[cfg["label_key_role"]]    = parsed.get("role") or parsed.get(cfg["label_key_role"]) or ""
                return res

        # 2️⃣ Labelled text fallback
        logger.warning(f"generate_module_label: JSON parse failed, trying text. Content: {content!r}")
        for line in [ln.strip() for ln in content.split("\n") if ln.strip()]:
            if re.search(r"module\s*name\s*:", line, re.I):
                res[cfg["label_key_name"]] = _to_snake_case(line.split(":", 1)[-1].strip())
            elif re.search(r"^role\s*:", line, re.I):
                res[cfg["label_key_role"]] = line.split(":", 1)[-1].strip()
            elif re.search(r"summary\s*:", line, re.I):
                res[cfg["label_key_summary"]] = line.split(":", 1)[-1].strip()

        # If we still got no name, it means both paths failed — log it clearly
        if res[cfg["label_key_name"]] == "uncategorized_module":
            logger.error(f"generate_module_label: both JSON and text parsing failed. Raw: {content!r}")

        return res

    except Exception as e:
        logger.error(f"generate_module_label failed: {e}")
        return {
            cfg["label_key_name"]:    f"cluster_{len(community_symbols)}_nodes",
            cfg["label_key_summary"]: "Automatic categorization unavailable.",
            cfg["label_key_role"]:    "",
        }

    finally:
        if original_instructions is not None:
            utility_agent.instructions = original_instructions

# ----------------------------------------- Migration events ---------------------------------------------

_scanner_event_helper = MigrationEventHelper(
    agent_name=AgentConstants.SCANNER_AGENT,
    event_name=AgentConstants.SCAN_MIGRATION_START,
)

_scanner_steps_sent_flags = {}
_scanner_logs_sent = {}

# Global Step 11 - Target Code Analysis identifiers (used across multiple functions)
TARGET_CODE_ANALYSIS_STEP_ID = AgentEventMessages.TARGET_CODE_ANALYSIS_STEP_ID
TARGET_CODE_ANALYSIS_STEP_NAME = AgentEventMessages.TARGET_CODE_ANALYSIS_STEP_NAME
TARGET_CODE_ANALYSIS_MSG_GROUP_ID = MigrationEvent.TARGET_CODE_ANALYSIS


def _notify_target_json_generated(user):
    logger.info("target_response.json generated")


def _notify_scanner_output_missing(user):
    logger.warning("Scanner output is missing")


def _send_migration_summary(migration_data, user):
    logger.info("Migration summary generated")


def _notify_migration_table(summary_message, user):
    if summary_message:
        # The generated UI summary is a dictionary.  Slice its serialized form
        # for logging instead of treating the dictionary as a sequence.
        logger.info(
            "Migration summary table generated: %s",
            json.dumps(summary_message, default=str)[:200],
        )


def _send_target_response(
    user,
    migration_dir: Path = None,
    step_id: str = None,
    step_name: str = None,
    msg_group_id: int = None,
):
    """Validate the target response artifact without publishing transport events."""
    target_response_file = Path("target_response.json")
    if migration_dir and (migration_dir / "target_response.json").exists():
        target_response_file = migration_dir / "target_response.json"
    if not target_response_file.exists():
        logger.warning("target_response.json not found at %s", target_response_file)
        return
    logger.info("Target response artifact available at %s", target_response_file)


def _notify_json_generated(user):
    logger.info("Scanner JSON artifact generated")


def _send_step_start(step_id: str, step_name: str, user, msg_group_id: int):
    _scanner_event_helper.send_step_start(step_id, step_name, user, msg_group_id)


def _send_step_description(step_id: str, step_name: str, user, msg_group_id: int):
    _scanner_event_helper.send_step_description(step_id, step_name, user, msg_group_id)


def _send_step_log(step_id: str, log_message: str, user, msg_group_id: int):
    _scanner_event_helper.send_step_log(step_id, log_message, user, msg_group_id)


def _send_step_logs_batch(step_id: str, logs: List[str], user, msg_group_id: int):
    for log_message in logs:
        _scanner_event_helper.send_step_log(step_id, log_message, user, msg_group_id)


def _send_step_result(step_id: str, step_name: str, result: str, user, msg_group_id: int):
    _scanner_event_helper.send_step_result(step_id, step_name, result, user, msg_group_id)


def _send_step_error(step_id: str, step_name: str, error_message: str, user, msg_group_id: int):
    _scanner_event_helper.send_step_error(step_id, step_name, error_message, user, msg_group_id)


def _notify_scanner_start(user, message):
    logger.info("Scanner started: %s", message)


def _send_language_event(user, tech):
    logger.info("Detected language: %s", tech.get("language", "unknown"))


def _send_framework_event(user, tech):
    logger.info("Detected framework: %s", tech.get("framework", "unknown"))


def _send_final_scan_metrics(user, syntactic_count, semantic_ir_count, non_convertible_count, tech):
    logger.info(
        "Scan metrics: syntactic=%s semantic_ir=%s excluded=%s language=%s framework=%s",
        syntactic_count, semantic_ir_count, non_convertible_count,
        tech.get("language", "Unknown"), tech.get("framework", "Unknown"),
    )
