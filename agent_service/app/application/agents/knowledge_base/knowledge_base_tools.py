import os
import lancedb
import logging
import json
from typing import Optional, Any, Tuple
from pathlib import Path
from agno.tools import tool
from agno.workflow.types import StepInput, StepOutput
from dotenv import load_dotenv
from app.domain.interfaces.i_json_artifact_repository import IJsonArtifactRepository
import app.application.agents.knowledge_base.knowledge_base_agent as kb
from app.infrastructure.utils.enums.msg_group import MsgGroup
from app.infrastructure.utils.user_context import current_user
from app.infrastructure.utils.Constants.app_constants import ArtifactType
from app.infrastructure.utils.Constants.agent_event import AgentEventMessages
from app.infrastructure.repositories.prompt_repository import fetch_prompt_from_db
from app.infrastructure.utils.file_utils import get_migration_directory, read_json_file
from app.infrastructure.utils.migration_context import migration_name_ctx, source_path_ctx
from app.infrastructure.repositories.json_artifact_repository import get_json_artifact_repository, SCOPE_SOURCE, SCOPE_TARGET
from app.infrastructure.utils.Constants.migration import MigrationConstants
from app.infrastructure.utils.Constants.validation_messages import ValidationMessages as VM
from app.infrastructure.utils.event_helper import MigrationEventHelper
from app.infrastructure.utils.enums.migration_event import MigrationEvent
load_dotenv()
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

_kb_event_helper = MigrationEventHelper(
    agent_name="knowledge_base",
    event_name="knowledge_base_started",
)

_json_artifact_repo: Optional[IJsonArtifactRepository] = None


def configure_knowledge_base_repositories(
    *,
    json_artifact_repo: Optional[IJsonArtifactRepository] = None,
) -> None:
    """Configure repository dependencies for knowledge base tools (for DI/testing)."""
    global _json_artifact_repo
    if json_artifact_repo is not None:
        _json_artifact_repo = json_artifact_repo


def _get_json_artifact_repo() -> IJsonArtifactRepository:
    global _json_artifact_repo
    if _json_artifact_repo is None:
        _json_artifact_repo = get_json_artifact_repository()
    return _json_artifact_repo

def load_json_to_knowledge(step_input: StepInput) -> StepOutput:
    """Load data from a JSON file and add it to the knowledge base."""
    try:
        migration_dir = get_migration_directory("", "")
        kg_path = str(migration_dir / "knowledge_graph.json")

        try:
            user = current_user.get()
            _kb_event_helper.send_step_start(
                AgentEventMessages.MIGRATION_PLAN_STEP_ID,
                AgentEventMessages.MIGRATION_PLAN_STEP_NAME,
                user,
                MigrationEvent.MIGRATION_PLAN,
            )
            _kb_event_helper.send_step_description(
                AgentEventMessages.MIGRATION_PLAN_STEP_ID,
                AgentEventMessages.MIGRATION_PLAN_STEP_NAME,
                user,
                MigrationEvent.MIGRATION_PLAN,
            )
            _kb_event_helper.send_step_log(
                AgentEventMessages.MIGRATION_PLAN_STEP_ID,
                "Loading knowledge graph into knowledge base...",
                user,
                MigrationEvent.MIGRATION_PLAN,
            )
        except Exception:
            pass

        with open(kg_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        symbols      = data["project_graph"]["symbols"]
        modules      = data["project_graph"]["modules"]
        dependencies = data["project_graph"]["dependencies"]
        file_paths   = data.get("Folder_structure", [])
        # Test hierarchy statistics are optional. Older/newer scanners may omit
        # them, but symbols/modules/dependencies must still be ingested.
        test_stats   = data.get("project_graph", {}).get("test_hierarchy_stats") or {}

        # ── Symbols ───────────────────────────────────────────────────────
        sym_documents = []
        for sym in symbols:
            content = (
                f"Symbol ID: {sym['symbol_id']}\n"
                f"Symbol Name: {sym['name']}\n"
                f"Symbol Summary: {sym['summary']}\n"
                f"Symbol Role: {sym['role']}"
            )
            meta_data = {
            "symbol_id":        sym.get("symbol_id", ""),
            "symbol_type":      sym.get("symbol_type", ""),
            "symbol_name":      sym.get("name", ""),
            "symbol_hash":      sym.get("symbol_hash", ""),
            "parent_symbol":    sym.get("parent_symbol", ""),   # ← add
            "module":           sym.get("module", ""),           # ← add
            "language":         sym.get("language", ""),
            "access":           sym.get("access", ""),
            "inherits":         sym.get("inherits", []),
            "line_range":       sym.get("line_range", ""),
            "file_path":        sym.get("file_path", ""),
            "calls":            sym.get("calls", ""),
            "dependencies":     sym.get("dependencies", ""),
            "parameters":       sym.get("parameters", ""),
            "return_type":      sym.get("return_type", ""),
            "summary":          sym.get("summary", ""),
            "meta":             sym.get("meta", {}) if isinstance(sym.get("meta", {}), dict) else {},
            "migration_status": "pending",
            "role":             sym.get("role", ""),
            "complexity":       sym.get("complexity"),
            "doc_type":         "source_symbol",
            "origin":           "existing",
        }
            sym_documents.append({
                "name":         sym.get("symbol_id"),
                "text_content": content,
                "metadata":     meta_data,
            })

        kb.source_knowledge.insert_many(sym_documents)
        logger.info(f"Inserted {len(sym_documents)} symbol documents")
        try:
            user = current_user.get()
            _kb_event_helper.send_step_log(
                AgentEventMessages.MIGRATION_PLAN_STEP_ID,
                f"Inserted {len(sym_documents)} symbols into knowledge base",
                user,
                MigrationEvent.MIGRATION_PLAN,
            )
        except Exception:
            pass

        # ── Test Thresholds Only ─────────────────────────────────────

        # Threshold metadata is optional. Always initialize the local so the
        # StepOutput below remains well-defined when test_hierarchy_stats or
        # suggested_thresholds are absent.
        thresholds = {}
        threshold_doc = None

        if test_stats:

            thresholds = test_stats.get(
                "suggested_thresholds",
                {}
            ) or {}

            logger.info(
                f"Found thresholds: {thresholds}"
            )

            if thresholds:

                threshold_doc = {
                    "name": "suggested_thresholds",

                    "text_content":
                        f"group={thresholds.get('group_threshold')} "
                        f"test={thresholds.get('test_threshold')} "
                        f"batch={thresholds.get('test_batch_size')}",

                    "metadata": {
                        "group_threshold":
                            thresholds.get("group_threshold"),

                        "test_threshold":
                            thresholds.get("test_threshold"),

                        "test_batch_size":
                            thresholds.get("test_batch_size"),

                        "doc_type":
                            "test_hierarchy_thresholds",

                        "origin":
                            "existing",
                    }
                }

        if threshold_doc:
            kb.source_knowledge.insert_many([threshold_doc])

            logger.info(
                f"Inserted hierarchy thresholds: "
                f"{threshold_doc['metadata']}"
            )
        else:
            logger.info(
                "No suggested_thresholds found in test_hierarchy_stats"
            )
            
        try:
            user = current_user.get()
            _kb_event_helper.send_step_log(
                AgentEventMessages.MIGRATION_PLAN_STEP_ID,
                f"Inserted {1 if threshold_doc else 0} hierarchy threshold document(s) into knowledge base",
                user,
                MigrationEvent.MIGRATION_PLAN,
            )
        except Exception:
            pass

        # ── Dependencies ──────────────────────────────────────────────────
        # New format: flat edge list {source, target, type, alias}
        dep_documents = []
        seen = set()

        for dep in dependencies:
            file_path = dep.get("source", "")
            name      = dep.get("target", "")
            dep_type  = dep.get("type", "third_party")
            alias     = dep.get("alias")

            if not file_path or not name:
                continue

            key = (file_path, name)
            if key in seen:
                continue
            seen.add(key)

            content = (
                f"Name: {name}\n"
                f"Type: {dep_type}\n"
                f"File path: {file_path}\n"
            )
            if alias:
                content += f"Alias: {alias}\n"

            meta_data = {
                "name":      name,
                "type":      dep_type,
                "alias":     alias,
                "file_path": file_path,
                "doc_type":  "source_dependencies",
            }

            unique_name = f"{Path(file_path).stem}_{name.replace(':', '_')}"
            dep_documents.append({
                "name":         unique_name,
                "text_content": content,
                "metadata":     meta_data,
            })

        kb.source_knowledge.insert_many(dep_documents)
        logger.info(f"Inserted {len(dep_documents)} dependency documents")
        try:
            user = current_user.get()
            _kb_event_helper.send_step_log(
                AgentEventMessages.MIGRATION_PLAN_STEP_ID,
                f"Inserted {len(dep_documents)} dependency entries into knowledge base",
                user,
                MigrationEvent.MIGRATION_PLAN,
            )
        except Exception:
            pass

        # ── Modules ───────────────────────────────────────────────────────
        mod_documents = []
        for mod, meta in modules.items():
            meta["module_name"] = mod
            meta["doc_type"]    = "module"
            content = (
                f"Module Name: {mod}\n"
                f"Module Summary: {meta.get('summary', '')}\n"
                f"Module Symbols: {', '.join(meta.get('symbols', []))}\n"
                f"Module Role: {meta.get('role', '')}"
            )
            mod_documents.append({
                "name":         mod,
                "text_content": content,
                "metadata":     meta,
            })

        kb.source_knowledge.insert_many(mod_documents)
        logger.info(f"Inserted {len(mod_documents)} module documents")
        try:
            user = current_user.get()
            _kb_event_helper.send_step_log(
                AgentEventMessages.MIGRATION_PLAN_STEP_ID,
                f"Inserted {len(mod_documents)} modules into knowledge base",
                user,
                MigrationEvent.MIGRATION_PLAN,
            )
        except Exception:
            pass

        # ── File paths ────────────────────────────────────────────────────
        path_documents = []
        for fp in file_paths:
            path_documents.append({
                "name":         str(fp),
                "text_content": f"File Path: {fp}",
                "metadata": {
                    "file_path": str(fp),
                    "doc_type":  "file_path",
                    "origin":    "existing",
                },
            })

        kb.source_knowledge.insert_many(path_documents)
        logger.info(f"Inserted {len(path_documents)} file path documents")
        try:
            user = current_user.get()
            _kb_event_helper.send_step_log(
                AgentEventMessages.MIGRATION_PLAN_STEP_ID,
                f"Inserted {len(path_documents)} file path entries into knowledge base",
                user,
                MigrationEvent.MIGRATION_PLAN,
            )
        except Exception:
            pass

        # ── Debug verification ────────────────────────────────────────────
        all_deps = kb.source_knowledge.search(
            query="*",
            filters={"doc_type": "source_dependencies"},
            search_type="hybrid",
            max_results=100,
        )
        logger.info(f"ALL source_dependencies in KB: {len(all_deps) if all_deps else 0}")
        for doc in (all_deps or []):
            logger.info(f"  -> dep: {doc.meta_data.get('name')} | file: {Path(doc.meta_data.get('file_path','')).name}")

        try:
            user = current_user.get()
            _kb_event_helper.send_step_result(
                AgentEventMessages.MIGRATION_PLAN_STEP_ID,
                AgentEventMessages.MIGRATION_PLAN_STEP_NAME,
                f"Knowledge base loaded — {len(sym_documents)} symbols, {len(dep_documents)} dependencies, {len(mod_documents)} modules, {len(path_documents)} file paths",
                user,
                MigrationEvent.MIGRATION_PLAN,
            )
        except Exception:
            pass

        return StepOutput(
            content=({
                f"symbols_data": {"symbols": symbols},
                f"modules_data": {"modules": modules},
                f"file_path": {"path": file_paths},
                f"hierarchy_thresholds": thresholds,
            }),
            success=True,
        )

    except Exception as e:
        logger.error(f"load_json_to_knowledge failed: {e}")
        try:
            user = current_user.get()
            _kb_event_helper.send_step_error(
                AgentEventMessages.MIGRATION_PLAN_STEP_ID,
                AgentEventMessages.MIGRATION_PLAN_STEP_NAME,
                f"Knowledge base loading failed: {str(e)}",
                user,
                MigrationEvent.MIGRATION_PLAN,
            )
        except Exception:
            pass
        return StepOutput(
            content=f"Failed to load JSON: {str(e)}",
            success=False,
            error=str(e),
        )
