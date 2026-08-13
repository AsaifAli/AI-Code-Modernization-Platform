import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

from app.infrastructure.utils.file_utils import get_migration_directory, read_json_file

_CODE_EXTENSIONS = {
    ".py", ".php", ".pl", ".pm", ".cgi", ".js", ".ts", ".tsx", ".jsx",
    ".java", ".cs", ".go", ".rb", ".cpp", ".c", ".h", ".hpp", ".kt",
    ".swift", ".scala", ".rs", ".sh",
}

_FUNC_PATTERNS = [
    re.compile(r"^\s*def\s+[A-Za-z_]\w*\s*\(", re.MULTILINE),
    re.compile(r"^\s*sub\s+[A-Za-z_]\w*\b", re.MULTILINE),
    re.compile(r"^\s*function\s+[A-Za-z_]\w*\s*\(", re.MULTILINE),
    re.compile(r"^\s*(?:public|private|protected|static|async|\s)+function\s+[A-Za-z_]\w*\s*\(", re.MULTILINE),
]

_IMPORT_PATTERNS = [
    re.compile(r"^\s*import\s+([\w\.\{\}\*,\s]+)", re.MULTILINE),
    re.compile(r"^\s*from\s+([\w\.]+)\s+import\s+", re.MULTILINE),
    re.compile(r"^\s*use\s+([\w:]+)", re.MULTILINE),
    re.compile(r"^\s*require(?:_once)?\s*\(?\s*[\"']?([^\"'\)\s]+)", re.MULTILINE),
]

_GENERIC_DIRS = {"src", "app", "lib", "libs", "code", "backend", "frontend", "server", "client", "api"}


def _safe_read_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = read_json_file(str(path))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _iter_code_files(root: Path) -> List[Path]:
    if not root.exists() or not root.is_dir():
        return []
    return [p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in _CODE_EXTENSIONS]


def _module_name(file_path: Path, root: Path) -> str:
    try:
        rel = file_path.relative_to(root)
    except Exception:
        rel = file_path
    parts = list(rel.parts)
    if len(parts) >= 2:
        if parts[0].lower() in _GENERIC_DIRS and len(parts) >= 3:
            return parts[1]
        return parts[0]
    if parts:
        return Path(parts[0]).stem or parts[0]
    return "unknown_module"


def _count_patterns(text: str, patterns: List[re.Pattern]) -> int:
    total = 0
    for p in patterns:
        total += len(p.findall(text))
    return total


def _extract_import_targets(text: str) -> List[str]:
    out: List[str] = []
    for p in _IMPORT_PATTERNS:
        for match in p.findall(text):
            if isinstance(match, tuple):
                candidate = " ".join(x for x in match if x)
            else:
                candidate = str(match)
            candidate = candidate.strip()
            if candidate:
                out.append(candidate)
    return out


def _analyze_codebase(root: Path) -> Dict[str, Any]:
    files = _iter_code_files(root)
    modules: Dict[str, Dict[str, Any]] = {}
    ext_counts: Dict[str, int] = {}
    total_loc = 0
    total_funcs = 0

    for f in files:
        try:
            text = f.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            text = ""
        loc = len([ln for ln in text.splitlines() if ln.strip()])
        funcs = _count_patterns(text, _FUNC_PATTERNS)
        imports = _extract_import_targets(text)
        module = _module_name(f, root)

        total_loc += loc
        total_funcs += funcs
        ext = f.suffix.lower() or "[no_ext]"
        ext_counts[ext] = ext_counts.get(ext, 0) + 1

        entry = modules.setdefault(
            module,
            {"files": 0, "loc": 0, "functions": 0, "imports": 0, "sample_files": [], "import_targets": []},
        )
        entry["files"] += 1
        entry["loc"] += loc
        entry["functions"] += funcs
        entry["imports"] += len(imports)
        if len(entry["sample_files"]) < 5:
            entry["sample_files"].append(str(f.relative_to(root)))
        entry["import_targets"].extend(imports[:20])

    ranked_modules = sorted(
        [{"module": k, **v} for k, v in modules.items()],
        key=lambda x: (x["loc"], x["functions"], x["files"]),
        reverse=True,
    )
    return {
        "root": str(root),
        "total_files": len(files),
        "total_loc": total_loc,
        "total_functions": total_funcs,
        "extensions": dict(sorted(ext_counts.items(), key=lambda kv: kv[1], reverse=True)),
        "modules": ranked_modules,
    }


def _to_doc(title: str, analysis: Dict[str, Any]) -> str:
    lines: List[str] = []
    lines.append(f"# {title}")
    lines.append("")
    lines.append("## Summary")
    lines.append(f"- Root: `{analysis.get('root', '')}`")
    lines.append(f"- Code Files: {analysis.get('total_files', 0)}")
    lines.append(f"- LOC: {analysis.get('total_loc', 0)}")
    lines.append(f"- Functions/Methods (estimated): {analysis.get('total_functions', 0)}")
    ext_items = analysis.get("extensions", {})
    ext_text = ", ".join(f"{k}:{v}" for k, v in list(ext_items.items())[:12]) or "N/A"
    lines.append(f"- Extensions: {ext_text}")
    lines.append("")
    lines.append("## Top Modules")
    lines.append("| Module | Files | LOC | Functions | Import Density |")
    lines.append("| --- | ---: | ---: | ---: | ---: |")
    for m in analysis.get("modules", [])[:20]:
        density = round(float(m.get("imports", 0)) / max(1, int(m.get("files", 0))), 2)
        lines.append(
            f"| {m.get('module')} | {m.get('files')} | {m.get('loc')} | {m.get('functions')} | {density} |"
        )
    lines.append("")
    return "\n".join(lines)


def _to_diagram(title: str, analysis: Dict[str, Any]) -> str:
    lines: List[str] = []
    lines.append("graph TD")
    lines.append(f"    ROOT[{title}]")
    for idx, m in enumerate(analysis.get("modules", [])[:12], start=1):
        name = str(m.get("module", f"module_{idx}")).replace("-", "_").replace(" ", "_")
        node = f"M{idx}_{name}"
        lines.append(f"    {node}[{m.get('module')}\\nfiles:{m.get('files')} loc:{m.get('loc')}]")
        lines.append(f"    ROOT --> {node}")
    return "\n".join(lines)


def _infer_source_root(migration_dir: Path) -> Path | None:
    source_response = _safe_read_json(migration_dir / "source_response.json")
    src = source_response.get("src_path")
    if isinstance(src, str) and src.strip():
        p = Path(src)
        if p.exists():
            return p

    source_scanner = _safe_read_json(migration_dir / "source_scanner_output.json")
    syn = source_scanner.get("syntactic_ast") or {}
    if isinstance(syn, dict) and syn:
        parents = [Path(k).parent for k in syn.keys() if isinstance(k, str) and k.strip()]
        if parents:
            common = Path(str(parents[0]))
            for p in parents[1:]:
                while common != common.parent and str(p).lower().find(str(common).lower()) != 0:
                    common = common.parent
            if common.exists():
                return common
    return None


def _to_comparison_doc(source_analysis: Dict[str, Any], target_analysis: Dict[str, Any], migration_name: str) -> str:
    lines: List[str] = []
    lines.append(f"# Migration Showcase Comparison: {migration_name}")
    lines.append("")
    lines.append("| Metric | Source | Migrated | Delta |")
    lines.append("| --- | ---: | ---: | ---: |")
    s_files = int(source_analysis.get("total_files", 0))
    t_files = int(target_analysis.get("total_files", 0))
    s_loc = int(source_analysis.get("total_loc", 0))
    t_loc = int(target_analysis.get("total_loc", 0))
    s_func = int(source_analysis.get("total_functions", 0))
    t_func = int(target_analysis.get("total_functions", 0))
    lines.append(f"| Files | {s_files} | {t_files} | {t_files - s_files:+} |")
    lines.append(f"| LOC | {s_loc} | {t_loc} | {t_loc - s_loc:+} |")
    lines.append(f"| Functions | {s_func} | {t_func} | {t_func - s_func:+} |")
    lines.append("")
    lines.append("## Notes")
    lines.append("- Counts are computed directly from code files in source/migrated folders.")
    lines.append("- Function count is heuristic pattern-based for multi-language projects.")
    lines.append("- Use this as review guidance, not strict compiler-level truth.")
    lines.append("")
    return "\n".join(lines)


def _save_showcase_artifacts(
    migration_dir: Path,
    source_doc: str,
    target_doc: str,
    source_diagram: str,
    target_diagram: str,
    comparison_doc: str,
) -> Dict[str, str]:
    out_dir = migration_dir / "showcase"
    out_dir.mkdir(parents=True, exist_ok=True)
    source_doc_path = out_dir / "source_documentation.md"
    target_doc_path = out_dir / "migrated_documentation.md"
    source_dia_path = out_dir / "source_diagram.mmd"
    target_dia_path = out_dir / "migrated_diagram.mmd"
    comparison_path = out_dir / "comparison_showcase.md"

    source_doc_path.write_text(source_doc, encoding="utf-8")
    target_doc_path.write_text(target_doc, encoding="utf-8")
    source_dia_path.write_text(source_diagram, encoding="utf-8")
    target_dia_path.write_text(target_diagram, encoding="utf-8")
    comparison_path.write_text(comparison_doc, encoding="utf-8")

    return {
        "source_documentation": str(source_doc_path),
        "migrated_documentation": str(target_doc_path),
        "source_diagram": str(source_dia_path),
        "migrated_diagram": str(target_dia_path),
        "comparison_showcase": str(comparison_path),
    }


def generate_showcase_bundle(migration_name: str, *, persist: bool = True) -> Dict[str, Any]:
    migration_dir = get_migration_directory(migration_name=migration_name, source_path="")
    migrated_dir = migration_dir / "migrated_code"
    if not migrated_dir.exists() or not migrated_dir.is_dir():
        return {
            "status": "not_ready",
            "migration_name": migration_name,
            "message": "migrated_code directory not found. Run migration first.",
            "required_paths": {"migrated_code_dir": str(migrated_dir)},
        }

    source_root = _infer_source_root(migration_dir)
    source_analysis = _analyze_codebase(source_root) if source_root and source_root.exists() else {
        "root": "",
        "total_files": 0,
        "total_loc": 0,
        "total_functions": 0,
        "extensions": {},
        "modules": [],
    }
    migrated_analysis = _analyze_codebase(migrated_dir)

    source_doc = _to_doc("Source Code Documentation", source_analysis)
    migrated_doc = _to_doc("Migrated Code Documentation", migrated_analysis)
    source_diagram = _to_diagram("Source Modules", source_analysis)
    migrated_diagram = _to_diagram("Migrated Modules", migrated_analysis)
    comparison_doc = _to_comparison_doc(source_analysis, migrated_analysis, migration_name)

    artifacts = {}
    if persist:
        artifacts = _save_showcase_artifacts(
            migration_dir,
            source_doc,
            migrated_doc,
            source_diagram,
            migrated_diagram,
            comparison_doc,
        )

    return {
        "status": "ready",
        "migration_name": migration_name,
        "source_available": bool(source_root and source_root.exists()),
        "source_root": str(source_root) if source_root else None,
        "migrated_root": str(migrated_dir),
        "source_metrics": {
            "files": source_analysis.get("total_files", 0),
            "loc": source_analysis.get("total_loc", 0),
            "functions": source_analysis.get("total_functions", 0),
        },
        "migrated_metrics": {
            "files": migrated_analysis.get("total_files", 0),
            "loc": migrated_analysis.get("total_loc", 0),
            "functions": migrated_analysis.get("total_functions", 0),
        },
        "artifacts": artifacts,
    }

