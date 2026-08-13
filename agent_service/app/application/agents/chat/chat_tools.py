import logging
import re
import json
from collections import Counter
from typing import Optional
from pathlib import Path
from agno.tools import tool
from app.application.agents.utility_agent import utility_agent
from app.infrastructure.utils.token_tracker import track_tokens
from app.infrastructure.utils.Agent_helpers.knowledge_base_helper import (
    kb_build_context,
    kb_build_file_context,
)
from app.infrastructure.utils.file_utils import get_migration_directory

logger = logging.getLogger(__name__)


_CODE_EXTENSIONS = {
    ".py", ".php", ".pl", ".pm", ".cgi", ".js", ".ts", ".tsx", ".jsx",
    ".java", ".cs", ".go", ".rb", ".cpp", ".c", ".h", ".hpp", ".kt",
    ".swift", ".scala", ".rs", ".sh",
}

_FUNCTION_PATTERNS = [
    re.compile(r"^\s*def\s+[A-Za-z_]\w*\s*\(", re.MULTILINE),
    re.compile(r"^\s*sub\s+[A-Za-z_]\w*\b", re.MULTILINE),  # Perl
    re.compile(r"^\s*function\s+[A-Za-z_]\w*\s*\(", re.MULTILINE),
    re.compile(
        r"^\s*(?:public|private|protected|static|async|\s)+function\s+[A-Za-z_]\w*\s*\(",
        re.MULTILINE,
    ),
]


def _safe_read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="ignore"))
    except Exception:
        return {}


def _infer_functions_from_ast_node(node: object) -> int:
    if not isinstance(node, dict):
        return 0
    count = 0
    node_type = str(node.get("type", "")).lower()
    if any(t in node_type for t in ("function", "method", "subroutine", "sub")):
        count += 1
    for child in node.get("children") or []:
        count += _infer_functions_from_ast_node(child)
    return count


def _build_project_summary_context(is_target: bool) -> str:
    """
    Load scanner output from current migration context and build aggregate project stats.
    """
    try:
        migration_dir = get_migration_directory("", "")
    except Exception:
        return ""

    scanner_file = migration_dir / (
        "target_scanner_output.json" if is_target else "source_scanner_output.json"
    )
    if not scanner_file.exists():
        return ""

    data = _safe_read_json(scanner_file)
    if not isinstance(data, dict):
        return ""

    syntactic_ast = data.get("syntactic_ast") or {}
    semantic_ir = data.get("semantic_ir") or []
    dependencies = data.get("dependencies") or data.get("all_dependencies") or []

    file_paths = list(syntactic_ast.keys()) if isinstance(syntactic_ast, dict) else []
    ext_counts = Counter(Path(p).suffix.lower() or "[no_ext]" for p in file_paths)
    total_files = len(file_paths)

    # Prefer semantic IR for method counts, fallback to AST node scan.
    functions_by_file: dict[str, int] = {}
    if isinstance(semantic_ir, list):
        for entry in semantic_ir:
            if not isinstance(entry, dict):
                continue
            fp = str(entry.get("file", "")).strip()
            if not fp:
                continue
            methods = entry.get("methods") or []
            functions_by_file[fp] = functions_by_file.get(fp, 0) + (
                len(methods) if isinstance(methods, list) else 0
            )

    if not functions_by_file and isinstance(syntactic_ast, dict):
        for fp, ast_obj in syntactic_ast.items():
            ast_root = ast_obj.get("ast") if isinstance(ast_obj, dict) else {}
            functions_by_file[fp] = _infer_functions_from_ast_node(ast_root)

    total_functions = sum(functions_by_file.values())
    top_files = sorted(
        functions_by_file.items(), key=lambda kv: kv[1], reverse=True
    )[:20]

    dep_count = 0
    if isinstance(dependencies, list):
        for d in dependencies:
            if isinstance(d, dict) and isinstance(d.get("deps"), list):
                dep_count += len(d["deps"])

    ext_summary = ", ".join(
        f"{ext}:{count}" for ext, count in sorted(ext_counts.items(), key=lambda x: (-x[1], x[0]))[:15]
    ) or "none"
    top_summary = "\n".join(
        f"- {fp}: {count}" for fp, count in top_files
    ) or "- none"

    return (
        "## PROJECT SUMMARY (SCANNER)\n"
        f"SCANNER_FILE: {scanner_file}\n"
        f"TOTAL_FILES: {total_files}\n"
        f"TOTAL_FUNCTIONS_OR_METHODS: {total_functions}\n"
        f"TOTAL_DEPENDENCIES: {dep_count}\n"
        f"SEMANTIC_IR_ENTRIES: {len(semantic_ir) if isinstance(semantic_ir, list) else 0}\n"
        f"FILE_EXTENSIONS: {ext_summary}\n"
        "TOP_FILES_BY_FUNCTION_COUNT:\n"
        f"{top_summary}\n"
    )


def _is_count_question(question: str) -> bool:
    q = (question or "").lower()
    return "how many" in q and ("file" in q or "function" in q or "method" in q)


def _count_functions(text: str) -> int:
    if not text:
        return 0
    total = 0
    for pattern in _FUNCTION_PATTERNS:
        total += len(pattern.findall(text))
    return total


def _scan_path_stats(path_value: str, max_files_to_scan: int = 800) -> dict:
    p = Path(path_value)
    if not p.exists():
        return {
            "exists": False,
            "is_dir": False,
            "total_files": 0,
            "scanned_code_files": 0,
            "estimated_functions": 0,
            "path": path_value,
        }

    files = [f for f in p.rglob("*") if f.is_file()] if p.is_dir() else [p]
    total_files = len(files)
    estimated_functions = 0
    scanned_code_files = 0

    for file_path in files[:max_files_to_scan]:
        if file_path.suffix.lower() not in _CODE_EXTENSIONS:
            continue
        scanned_code_files += 1
        try:
            text = file_path.read_text(encoding="utf-8", errors="ignore")
            estimated_functions += _count_functions(text)
        except Exception:
            continue

    return {
        "exists": True,
        "is_dir": p.is_dir(),
        "total_files": total_files,
        "scanned_code_files": scanned_code_files,
        "estimated_functions": estimated_functions,
        "path": str(p),
        "scan_capped": total_files > max_files_to_scan,
    }


def _format_fs_context(stats: dict) -> str:
    if not stats or not stats.get("exists"):
        return ""
    cap_note = " (scan capped)" if stats.get("scan_capped") else ""
    return (
        "## FILESYSTEM SUMMARY\n"
        f"PATH: {stats.get('path')}\n"
        f"IS_DIRECTORY: {stats.get('is_dir')}\n"
        f"TOTAL_FILES: {stats.get('total_files')}\n"
        f"SCANNED_CODE_FILES: {stats.get('scanned_code_files')}{cap_note}\n"
        f"ESTIMATED_FUNCTIONS: {stats.get('estimated_functions')}\n"
    )


def ask_kb_impl(
    question: str,
    source_file_path: Optional[str] = None,
    is_target: bool = False,
) -> str:
    """
    KB-backed Q&A tool.
    - Uses KB vector search (chunk-based) rather than passing full syntactic AST.
    - If source_file_path is provided, scopes retrieval to that file's chunks.
    """
    question = (question or "").strip()
    if not question:
        return "Please provide a question."

    fs_stats = None
    if source_file_path:
        try:
            fs_stats = _scan_path_stats(source_file_path)
        except Exception:
            fs_stats = None

    # Deterministic answer for "how many files/functions" style questions.
    if fs_stats and fs_stats.get("exists") and _is_count_question(question):
        scope = "directory" if fs_stats.get("is_dir") else "file"
        return (
            f"Scope: `{fs_stats.get('path')}` ({scope}).\n"
            f"- Total files: {fs_stats.get('total_files')}\n"
            f"- Estimated functions/methods: {fs_stats.get('estimated_functions')}\n"
            f"- Code files scanned: {fs_stats.get('scanned_code_files')}\n"
            f"Note: function count is estimated from code patterns."
        )

    if source_file_path:
        path_obj = Path(source_file_path)
        if path_obj.exists() and path_obj.is_dir():
            context = kb_build_context(
                queries=[question, path_obj.name, "SEMANTIC IR", "DEPENDENCY:", "AST JSON"],
                filters={"is_target": bool(is_target)},
                max_results_per_query=10,
                max_chars=18000,
            )
        else:
            context = kb_build_file_context(
                question=question,
                source_file_path=source_file_path,
                is_target=is_target,
                max_results=40,
                max_chars=18000,
            )
    else:
        context = kb_build_context(
            queries=[question, "SEMANTIC IR", "DEPENDENCY:", "AST JSON"],
            filters={"is_target": bool(is_target)},
            max_results_per_query=10,
            max_chars=18000,
        )

    project_summary_context = _build_project_summary_context(bool(is_target))
    fs_context = _format_fs_context(fs_stats) if fs_stats else ""
    combined_context = "\n\n".join(
        c for c in [project_summary_context, fs_context, context] if c
    )

    prompt = f"""
You are a helpful codebase assistant. Answer ONLY from the provided KB context.
If the answer is not supported by context, say what is missing and how to locate it.

QUESTION:
{question}

KB CONTEXT:
{combined_context or "[No KB context found. Ensure KB agent has indexed the project.]"}

RESPONSE RULES:
- Be direct and specific.
- Prefer quoting exact identifiers, file paths, class names, method names when present.
- If user asks "how many functions/files", use FILESYSTEM SUMMARY counts when available.
- Use PROJECT SUMMARY (SCANNER) for project-wide totals and file-extension breakdowns.
"""

    utility_agent.output_schema = None
    resp = utility_agent.run(prompt)
    track_tokens(resp, source="chat:kb_query")
    return getattr(resp, "content", str(resp)).strip()


@tool
def ask_kb(
    question: str,
    source_file_path: Optional[str] = None,
    is_target: bool = False,
) -> str:
    """Agno tool wrapper around the plain KB Q&A helper."""
    return ask_kb_impl(
        question=question,
        source_file_path=source_file_path,
        is_target=is_target,
    )

