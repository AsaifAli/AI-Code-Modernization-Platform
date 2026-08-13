import re
import json
import logging
from pathlib import Path
from textwrap import dedent
from dotenv import load_dotenv
from typing import Dict, List, Any, Optional
from app.application.agents.planning.planning_agent import planning_agent
from app.infrastructure.utils.event_helper import MigrationEventHelper
from app.infrastructure.utils.file_utils import get_migration_directory
from app.infrastructure.utils.enums.migration_event import MigrationEvent
from app.infrastructure.utils.shared_utills import extract_target_tech_stack
from app.infrastructure.utils.Constants.agent_event import AgentEventMessages
from app.infrastructure.repositories.prompt_repository import fetch_prompt_from_db
from app.infrastructure.utils.file_utils import read_json_file, parse_json_response
from app.infrastructure.utils.migration_context import (
    migration_name_ctx,
    target_language_ctx,
    target_framework_ctx,
    target_architecture_ctx,
    is_frontend_ctx,
    target_frontend_ctx,
    target_frontend_architecture_ctx,
    description_ctx,
)
from app.infrastructure.utils.file_utils import read_json_file, parse_json_response, _get_runtime_tech_context
from app.infrastructure.utils.migration_context import migration_name_ctx,target_language_ctx
from app.application.agents.planning.planning_agent import planning_agent
from app.infrastructure.utils.token_tracker import track_tokens
from app.infrastructure.utils.Constants.app_constants import AgentConstants, ArtifactType
load_dotenv()
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

from app.infrastructure.utils.symbol_split_policy import (
    build_relationship_index,
    relationship_metrics,
    build_split_instructions,
    policy_for_symbol,
)

__all__ = [
    'read_source_lines',
    'parse_json_robust',
    'analyse_module_symbols',
    '_planning_event_helper',
    '_send_planning_step_start',
    '_send_planning_step_description',
    '_send_planning_step_log',
    '_send_planning_step_result',
    '_load_existing_plan',
    '_extract_json',
    '_hierarchy_representative_sids',
    '_HIERARCHY_TYPES',
]

# -------------------------- File Utils -------------------------------------
def read_source_lines(file_path: str, start: int, end: int) -> str:
    """
    Reads source lines from file_path between start and end (1-based, inclusive).
    Returns raw source code string.
    """
    try:
        with open(file_path, 'r', encoding="utf-8") as f:
            lines = f.readlines()
        selected = lines[start - 1:end]
        return ''.join(selected)
    except Exception as e:
        print(f"  ⚠️  Could not read {file_path} lines {start}-{end}: {e}")
        return ""
    
def _load_existing_plan() -> dict | None:
    """DB-first, file fallback. Returns plan dict if already exists, else None."""
    _mig = migration_name_ctx.get("")
    if _mig:
        try:
            from app.infrastructure.repositories.json_artifact_repository import fetch_json_artifact as _fetch_artifact
            plan = _fetch_artifact(_mig, ArtifactType.MIGRATION_PLAN)
            if plan:
                logger.info("Existing migration_plan found in DB — skipping planning")
                return plan
        except Exception as exc:
            logger.warning("Could not load migration_plan from DB: %s", exc)
    try:
        plan_file = Path(get_migration_directory()) / "migration_plan.json"
        if plan_file.exists():
            plan = json.loads(plan_file.read_text(encoding="utf-8"))
            if plan:
                logger.info("Existing migration_plan.json found on disk — skipping planning")
                return plan
    except Exception as exc:
        logger.warning("Could not read migration_plan.json: %s", exc)
    return None
    
def parse_json_robust(text: str, array_mode: bool = False):
    """
    Strips fences, tries direct parse, walks for balanced value,
    attempts truncation repair, and now also handles concatenated
    JSON objects by collecting ALL top-level values and merging them.
    """
    if not text:
        raise ValueError("Empty input")

    # 1. Strip markdown fences
    text = re.sub(r"```(?:json)?", "", text, flags=re.IGNORECASE)
    text = re.sub(r"```", "", text)
    text = text.strip()

    # 2. Fast path
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 3. Collect ALL top-level balanced JSON values (handles concatenated objects)
    def _iter_top_level(src: str):
        """Yield every top-level balanced JSON substring found in src."""
        i = 0
        while i < len(src):
            if src[i] not in ("{", "["):
                i += 1
                continue
            open_c  = src[i]
            close_c = "}" if open_c == "{" else "]"
            depth, in_str, escape = 0, False, False
            for j, ch in enumerate(src[i:], i):
                if escape:
                    escape = False
                    continue
                if ch == "\\" and in_str:
                    escape = True
                    continue
                if ch == '"':
                    in_str = not in_str
                    continue
                if in_str:
                    continue
                if ch == open_c:
                    depth += 1
                elif ch == close_c:
                    depth -= 1
                    if depth == 0:
                        yield src[i : j + 1]
                        i = j + 1
                        break
            else:
                # Unbalanced — try repair if it's an array
                fragment = src[i:]
                repaired = _repair_array(fragment) if open_c == "[" else None
                if repaired:
                    yield repaired
                break

    def _repair_array(src: str) -> str | None:
        start = src.find("[")
        if start == -1:
            return None
        depth, in_str, escape = 0, False, False
        last_complete_end = -1
        for i, ch in enumerate(src[start:], start):
            if escape:
                escape = False
                continue
            if ch == "\\" and in_str:
                escape = True
                continue
            if ch == '"':
                in_str = not in_str
                continue
            if in_str:
                continue
            if ch in ("{", "["):
                depth += 1
            elif ch in ("}", "]"):
                depth -= 1
                if depth == 1 and ch == "}":
                    last_complete_end = i + 1
        if depth == 0:
            return None  # already balanced
        if last_complete_end > 0:
            return src[start:last_complete_end].rstrip().rstrip(",") + "\n]"
        return "[]"

    # 4. Parse each top-level value; merge dicts, extend lists
    candidates = []
    for fragment in _iter_top_level(text):
        cleaned = re.sub(r",(\s*[}\]])", r"\1", fragment)  # trailing commas
        try:
            candidates.append(json.loads(cleaned))
        except json.JSONDecodeError:
            pass

    if not candidates:
        raise ValueError(f"No valid JSON found in: {text[:200]!r}")

    if len(candidates) == 1:
        return candidates[0]

    # Multiple top-level values: merge if all dicts, extend if all lists
    if all(isinstance(c, dict) for c in candidates):
        merged = {}
        for c in candidates:
            merged.update(c)
        return merged

    if all(isinstance(c, list) for c in candidates):
        return [item for c in candidates for item in c]

    # Mixed — return the largest candidate
    return max(candidates, key=lambda c: len(json.dumps(c)))

def _sanitize_json_string(raw: str) -> str:
    """
    Fix common LLM JSON violations:
    - Literal unescaped newlines inside string values
    - Trailing commas before } or ]
    """
    # Replace literal newlines inside JSON strings with \n escape
    # Only inside quoted strings — use a state machine approach
    result = []
    in_string = False
    escape_next = False
    for char in raw:
        if escape_next:
            result.append(char)
            escape_next = False
            continue
        if char == "\\":
            result.append(char)
            escape_next = True
            continue
        if char == '"':
            in_string = not in_string
            result.append(char)
            continue
        if in_string and char == "\n":
            result.append("\\n")   # escape the literal newline
            continue
        if in_string and char == "\r":
            result.append("\\r")
            continue
        if in_string and char == "\t":
            result.append("\\t")
            continue
        result.append(char)
    sanitized = "".join(result)
    # Remove trailing commas
    sanitized = re.sub(r",\s*}", "}", sanitized)
    sanitized = re.sub(r",\s*]", "]", sanitized)
    return sanitized

def _extract_json(raw: str) -> dict:
    """Extract the first valid JSON object from raw text, ignoring surrounding prose."""
    # Try direct parse first
    try:
        return json.loads(raw.strip())
    except json.JSONDecodeError:
        pass
    # Try after sanitizing unescaped newlines/control chars in strings
    try:
        return json.loads(_sanitize_json_string(raw.strip()))
    except json.JSONDecodeError:
        pass
    # Find first { ... } block, sanitize, then parse
    start = raw.find("{")
    while start != -1:
        end = raw.rfind("}")
        while end > start:
            candidate = _sanitize_json_string(raw[start:end + 1])
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                end = raw.rfind("}", start, end)
        start = raw.find("{", start + 1)
    return {}

_HIERARCHY_TYPES = {"preamble", "section", "group", "test", "teardown"}

def _hierarchy_representative_sids(
    symbol_list:     list,
    group_threshold: int,
    test_threshold:  int = 14,  
) -> set[str]:
    """
    Return only the symbol_ids that will generate their own plan entry.
    Absorbed symbols (groups inside section-level plans, all tests) are excluded
    so generate_symbols_transformation skips their LLM calls entirely.
    """
    sec_grp_count: dict[str, int] = {}

    for sym in symbol_list:
        meta   = sym.get("meta_data", sym)
        t      = (meta.get("ast_node_type") or meta.get("symbol_type") or "").lower()
        sid    = sym.get("symbol_id") or meta.get("symbol_id", "")
        parent = meta.get("parent_symbol", "")
        if t == "section":
            sec_grp_count.setdefault(sid, 0)
        elif t == "group" and parent:
            sec_grp_count[parent] = sec_grp_count.get(parent, 0) + 1

    reps: set[str] = set()
    for sym in symbol_list:
        meta   = sym.get("meta_data", sym)
        t      = (meta.get("ast_node_type") or meta.get("symbol_type") or "").lower()
        sid    = sym.get("symbol_id") or meta.get("symbol_id", "")
        parent = meta.get("parent_symbol", "")

        if t not in _HIERARCHY_TYPES:
            reps.add(sid)                                              # regular code
        elif t in {"preamble", "teardown"}:
            reps.add(sid)                                              # always own plan
        elif t == "section" and sec_grp_count.get(sid, 0) <= group_threshold:
            reps.add(sid)                                              # section-level plan
        elif t == "group" and sec_grp_count.get(parent, 0) > group_threshold:
            reps.add(sid)                                              # group-level plan
        # tests → always absorbed, never analyzed

    return reps

def analyse_module_symbols(
    mod_name:    str,
    mod_summary: str,
    mod_symbols: list[dict],
    plan_id_map: dict[str, str],
    file_paths:  list,
) -> dict[str, dict]:
    """
    Analyze symbols and generate migration plan using target tech_data + file_paths context.
    """
    if not mod_symbols:
        return {}

    expected_ids = [s.get("symbol_id", "") for s in mod_symbols]
    # Relationship cardinality is derived from the symbol graph, not inferred
    # from LOC. This supports one-to-many, many-to-one and many-to-many cases.
    module_graph = build_relationship_index(mod_symbols)
    module_graph_metrics = relationship_metrics(module_graph)
    runtime_tech = _get_runtime_tech_context()

    def _build_prompt(symbols: list[dict], previous_result: dict | None = None) -> str:

        tech_summary = (
            f"Target Language : {runtime_tech['language']}\n"
            f"Framework       : {runtime_tech['framework'] or 'None'}\n"
            f"Architecture    : {runtime_tech['architecture'] or 'Unknown'}\n"
        )
        # Target Folder Context
        file_context = "Target Folder structure\n"
        file_context += "\n".join(f"  - {p}" for p in file_paths)

        lines = []
        for i, s in enumerate(symbols, 1):
            sid = s.get("symbol_id", "")
            plan_id = plan_id_map.get(sid, "plan_000")
            meta = s.get("meta_data", s)
            lr = meta.get("line_range") or s.get("line_range") or {}
            start = lr.get("start") or lr.get("start_line") or 0
            end = lr.get("end") or lr.get("end_line") or 0
            line_cnt = max(0, end - start + 1)

            symbol_type = (
                s.get("symbol_type")
                or ""
            ).lower()

            is_test_symbol = symbol_type == "test_script"

            policy = policy_for_symbol(s, module_graph_metrics)
            if is_test_symbol:
                transformation_directive = "1:1"
            elif policy["action"] == "split":
                transformation_directive = "Split"
            elif policy["action"] == "review-or-split":
                transformation_directive = "Review/Split"
            else:
                transformation_directive = "1:1"
            entry = (
                f"{i}. symbol_id: {sid}"
                f" | plan_id: {plan_id}"
                f" | name: {s.get('name') or s.get('symbol_name') or ''}"
                f" | summary: {s.get('summary', '')}"
                f" | role: {s.get('role', '')}"
                f" | lines: {line_cnt} (source_start={start}, source_end={end})"
                f" | TRANSFORMATION (MANDATORY): {transformation_directive}"
            )
            if policy["action"] in {"split", "review-or-split"} and not is_test_symbol:
                src = read_source_lines(file_path=meta.get("file_path") or s.get("file_path", ""), start=start, end=end)
                split_guidance = build_split_instructions(s, module_graph_metrics)

                entry += (
                    f"\n {split_guidance}\n"
                    f"\n This symbol MUST be split into multiple parts. Returning empty parts is INVALID.\n"
                    "   Split based on natural logical boundaries present in the code.\n"
                    "   Each part should represent a cohesive unit of behavior.\n"
                    "   STRICT RULES (MUST FOLLOW):"
                    "    - start_line MUST be >= original start"
                    "    - end_line MUST be <= original end"
                    "    - start_line MUST be <= end_line"
                    "    - Parts MUST fully cover the range from start → end"
                    "    - NO part can have start > end"
                    "    - If violated → response is INVALID"
                    "   - Reasonable balance in size across parts\n"
                    "   source snippet:\n"
                    f"{src}"
                )
            lines.append(entry)

        first_sid = expected_ids[0] if expected_ids else "<symbol_id>"

        example = (
        "{\n"
        f'  "{first_sid}": {{\n'
        f'    "target_symbol_name": "symbol_name",\n'
        f'    "target_symbol_type": "symbol",\n'
        f'    "target_file": "file_path\\file_name.ext",\n'
        f'    "transformation": "Split",\n'
        f'    "parts": [\n'
        f'      {{"part_id": "plan_001_part_1", "target_symbol_name": "init", "target_symbol_type": "function", "start_line": 10, "end_line": 80}},\n'
        f'      {{"part_id": "plan_001_part_2", "target_symbol_name": "process", "target_symbol_type": "function", "start_line": 81, "end_line": 150}}\n'
        f'    ]\n'
        "  }\n"
        "}"
    )

        retry_header = ""
        locked_names = ""
        if previous_result:
            retry_header = (
                "RETRY — Previous attempt returned parts: [] for Split symbols. "
                "That is INVALID. You MUST define parts for every Split symbol.\n\n"
            )
            locked = [
                f"  {sid}: target_symbol_name={prev.get('target_symbol_name', '')} | target_file={prev.get('target_file', '')}"
                for sid, prev in previous_result.items()
                if sid in {s.get("symbol_id") for s in symbols}
            ]
            if locked:
                locked_names = (
                    "KEEP THESE UNCHANGED (only define parts):\n"
                    + "\n".join(locked)
                    + "\n\n"
                )

        return (
            retry_header
            + f"Module Name: {mod_name}\n"
            f"Module Summary: {mod_summary}\n\n"
            f"PROJECT CONTEXT:\n{tech_summary}\n"
            f"Target Folder structure:\n{file_context}\n\n"
            + locked_names
            + f"Symbols to migrate ({len(symbols)}):\n"
            + "\n".join(lines)
            + "\n\n"
            "Return ONLY a flat JSON object where each key is a symbol_id.\n"
            f"Expected symbol_ids: {expected_ids}\n\n"
            f"Example output format:\n{example}"
        )
    
    def _extract_dict(response) -> dict:
        content = (
            response.content if hasattr(response, "content")
            else response.choices[0].message.content if hasattr(response, "choices")
            else str(response)
        )
        parsed = parse_json_robust(str(content))
        return parsed if isinstance(parsed, dict) else {}

    # Main execution with retry
    result: dict[str, dict] = {}
    missing_ids = list(expected_ids)

    for attempt in range(1, 4):
        pending = [s for s in mod_symbols if s.get("symbol_id") in missing_ids]
        if not pending:
            break

        try:
            prompt = _build_prompt(
                symbols=pending,
                previous_result=result if attempt > 1 else None,
            )
            response = planning_agent.run(prompt)
            track_tokens(response, source="planning:folder_structure")
            batch = _extract_dict(response)
            # An LLM can produce a valid top-level JSON object while returning
            # a scalar for an individual symbol.  Downstream planning requires
            # every symbol value to be an object, so discard malformed entries
            # and let the normal retry/default path handle them.
            normalized_batch = {}
            for sid, entry in batch.items():
                if sid not in expected_ids:
                    continue
                if not isinstance(entry, dict):
                    logger.warning(
                        "Ignoring malformed plan entry for %s: expected object, got %s",
                        sid,
                        type(entry).__name__,
                    )
                    continue
                normalized_entry = dict(entry)
                parts = normalized_entry.get("parts", [])
                normalized_entry["parts"] = (
                    [part for part in parts if isinstance(part, dict)]
                    if isinstance(parts, list)
                    else []
                )
                normalized_batch[sid] = normalized_entry
            result.update(normalized_batch)
        except Exception as e:
            print(f"  ⚠️ Attempt {attempt} failed for module '{mod_name}': {e}")
            if attempt == 3:
                break
            continue

        # A Split symbol with no parts is also considered incomplete
        def _is_incomplete(sid: str) -> bool:
            if sid not in result:
                return True
            sym = next((s for s in mod_symbols if s.get("symbol_id") == sid), {})
            meta = sym.get("meta_data", sym)
            lr = meta.get("line_range") or sym.get("line_range") or {}
            lc = max(0, (lr.get("end", 0) or 0) - (lr.get("start", 0) or 0) + 1)
            sym_policy = policy_for_symbol(sym, module_graph_metrics)
            if sym_policy["action"] in {"split", "review-or-split"} and not result[sid].get("parts"):
                print(
                    f"  ⚠️  Retry: {sid} is {lc} lines and was flagged "
                    f"{sym_policy['action']} but has no parts"
                )
                return True
            return False

        missing_ids = [sid for sid in expected_ids if _is_incomplete(sid)]
        if not missing_ids:
            break

    return result
# ---------------------------- Migration events -----------------------------

_planning_event_helper = MigrationEventHelper(
    agent_name=AgentConstants.PLANNING_AGENT,
    event_name=AgentConstants.PLANNING_AGENT_STARTED
)

_planning_steps_sent_flags = {}

_planning_logs_sent = {}

migration_plan_step_id = AgentEventMessages.MIGRATION_PLAN_STEP_ID
migration_plan_step_name = AgentEventMessages.MIGRATION_PLAN_STEP_NAME
migration_plan_msg_group_id = MigrationEvent.MIGRATION_PLAN

def _send_planning_step_start(step_id: str, step_name: str, user, msg_group_id: int):
    """Send step start event: 'Now I am picking the step: {stepName}' (TITLE) - Only once per step per migration"""
    global _planning_steps_sent_flags
    
    migration_name = None
    
    if step_id == AgentEventMessages.MIGRATION_PLAN_STEP_ID:
        migration_name = migration_name_ctx.get(None)
        if migration_name:
            if migration_name not in _planning_steps_sent_flags:
                _planning_steps_sent_flags[migration_name] = {
                    AgentEventMessages.MIGRATION_PLAN_STEP_START_SENT_FLAG: False,
                    AgentEventMessages.MIGRATION_PLAN_STEP_DESCRIPTION_SENT_FLAG: False
                }
            
            if _planning_steps_sent_flags[migration_name].get(AgentEventMessages.MIGRATION_PLAN_STEP_START_SENT_FLAG, False):
                return  
    
    _planning_event_helper.send_step_start(step_id, step_name, user, msg_group_id)
    
    if step_id == AgentEventMessages.MIGRATION_PLAN_STEP_ID and migration_name:
        _planning_steps_sent_flags[migration_name][AgentEventMessages.MIGRATION_PLAN_STEP_START_SENT_FLAG] = True

def _send_planning_step_description(step_id: str, step_name: str, user, msg_group_id: int):
    """Send step description: 'This step analyzes and processes {stepName}...' (SUBTITLE) - Only once per step per migration"""
    global _planning_steps_sent_flags
    
    migration_name = None
    
    if step_id == AgentEventMessages.MIGRATION_PLAN_STEP_ID:
        migration_name = migration_name_ctx.get(None)
        if migration_name:
            if migration_name not in _planning_steps_sent_flags:
                _planning_steps_sent_flags[migration_name] = {
                    AgentEventMessages.MIGRATION_PLAN_STEP_START_SENT_FLAG: False,
                    AgentEventMessages.MIGRATION_PLAN_STEP_DESCRIPTION_SENT_FLAG: False
                }
            
            if _planning_steps_sent_flags[migration_name].get(AgentEventMessages.MIGRATION_PLAN_STEP_DESCRIPTION_SENT_FLAG, False):
                return 
            
            if not _planning_steps_sent_flags[migration_name].get(AgentEventMessages.MIGRATION_PLAN_STEP_START_SENT_FLAG, False):
                _send_planning_step_start(step_id, step_name, user, msg_group_id)
    
    _planning_event_helper.send_step_description(step_id, step_name, user, msg_group_id)
    
    if step_id == AgentEventMessages.MIGRATION_PLAN_STEP_ID and migration_name:
        _planning_steps_sent_flags[migration_name][AgentEventMessages.MIGRATION_PLAN_STEP_DESCRIPTION_SENT_FLAG] = True

def _send_planning_step_log(step_id: str, log_message: str, user, msg_group_id: int):
    """Send a single log message for a step (LOG) - Prevents ANY duplicate logs for ANY step"""
    global _planning_logs_sent
    
    migration_name = migration_name_ctx.get(None)
    
    if migration_name:
        if migration_name not in _planning_logs_sent:
            _planning_logs_sent[migration_name] = set()
        
        log_key = (step_id, log_message)
        
        if log_key in _planning_logs_sent[migration_name]:
            return
        
        _planning_logs_sent[migration_name].add(log_key)
    
    _planning_event_helper.send_step_log(step_id, log_message, user, msg_group_id)

def _send_planning_step_result(step_id: str, step_name: str, result_message: str, user, msg_group_id: int):
    """Send step result/summary (RESULT)"""
    _planning_event_helper.send_step_result(step_id, step_name, result_message, user, msg_group_id)
