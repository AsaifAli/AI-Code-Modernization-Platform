import json
import os
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple
from urllib.parse import quote
from dotenv import load_dotenv
from app.infrastructure.utils.Constants.app_constants import PathConstants
from app.infrastructure.utils.file_utils import get_migration_directory, read_json_file

load_dotenv()
logger = logging.getLogger(__name__)

_GENERIC_MODULE_DIRS = {
    "src", "app", "apps", "lib", "libs", "code", "services", "service",
    "backend", "frontend", "api", "server", "client",
}

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
    re.compile(r"^\s*import\s+[\w\.\{\}\*,\s]+", re.MULTILINE),
    re.compile(r"^\s*from\s+[\w\.]+\s+import\s+", re.MULTILINE),
    re.compile(r"^\s*use\s+[\w:]+", re.MULTILINE),
    re.compile(r"^\s*require(?:_once)?\s*\(", re.MULTILINE),
]

_COMPLEXITY_TOKENS = [" if ", " elif ", " else", " for ", " while ", " catch", " except", " switch", " case ", "&&", "||"]
_UNSUPPORTED_TOKENS = ["eval(", "exec(", "goto ", "shell_exec(", "backticks", "legacy", "todo", "fixme"]


def _safe_read_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = read_json_file(str(path))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _module_name_from_path(file_path: str, root_path: str) -> str:
    try:
        p = Path(file_path)
        root = Path(root_path) if root_path else None
        if root and p.is_absolute():
            try:
                rel = p.relative_to(root)
            except Exception:
                rel = p
        else:
            rel = p
        parts = [seg for seg in rel.parts if seg not in (".", "")]
        if len(parts) >= 2:
            first = parts[0].lower()
            if first in _GENERIC_MODULE_DIRS and len(parts) >= 3:
                return parts[1]
            return parts[0]
        if parts:
            stem = Path(parts[0]).stem
            return stem or parts[0]
    except Exception:
        pass
    return "unknown_module"


def _risk_label(score: float) -> str:
    if score >= 67:
        return "High"
    if score >= 34:
        return "Medium"
    return "Low"


def _risk_emoji(label: str) -> str:
    return {"High": "🔴", "Medium": "🟡", "Low": "🟢"}.get(label, "🟢")


def _severity_from_delta(delta: int) -> str:
    if delta >= 20:
        return "High"
    if delta >= 8:
        return "Medium"
    return "Low"


def _normalize(value: float, max_value: float) -> float:
    if max_value <= 0:
        return 0.0
    return min(100.0, max(0.0, (value / max_value) * 100.0))


def _load_mapping(migration_dir: Path) -> List[Dict[str, Any]]:
    mapping_file = migration_dir / "file_mapping.json"
    if not mapping_file.exists():
        return []
    data = _safe_read_json(mapping_file)
    if isinstance(data, list):
        return [m for m in data if isinstance(m, dict)]
    if isinstance(data, dict) and isinstance(data.get("mappings"), list):
        return [m for m in data["mappings"] if isinstance(m, dict)]
    return []


def _build_module_stats(file_data: List[Dict[str, Any]], root_path: str) -> Dict[str, Dict[str, Any]]:
    modules: Dict[str, Dict[str, Any]] = {}
    for f in file_data or []:
        fp = str(f.get("filePath") or "")
        module = _module_name_from_path(fp, root_path)
        entry = modules.setdefault(
            module,
            {
                "files": 0,
                "loc": 0,
                "functions": 0,
                "dependencies": 0,
                "file_paths": [],
                "test_files": 0,
                "extensions": {},
            },
        )
        entry["files"] += 1
        entry["loc"] += int(f.get("lineOfCode") or 0)
        entry["functions"] += int(f.get("functionCount") or 0)
        deps = f.get("dependencies_libraries") or []
        entry["dependencies"] += len(deps) if isinstance(deps, list) else 0
        entry["file_paths"].append(fp)
        file_name = str(f.get("fileName") or "").lower()
        if "test" in file_name or "spec" in file_name:
            entry["test_files"] += 1
        ext = Path(fp).suffix.lower() or "[no_ext]"
        entry["extensions"][ext] = entry["extensions"].get(ext, 0) + 1
    return modules


def _map_complexity_by_path(complexity_data: List[Dict[str, Any]]) -> Dict[str, float]:
    out: Dict[str, float] = {}
    for item in complexity_data or []:
        if not isinstance(item, dict):
            continue
        path = str(item.get("filePath") or "")
        try:
            score = float(item.get("complexityScore") or 0)
        except Exception:
            score = 0.0
        if path:
            out[path] = score
    return out


def _count_with_patterns(text: str, patterns: List[re.Pattern]) -> int:
    if not text:
        return 0
    total = 0
    for p in patterns:
        total += len(p.findall(text))
    return total


def _estimate_complexity_score(text: str) -> float:
    if not text:
        return 0.0
    low = text.lower()
    base = 0.0
    for token in _COMPLEXITY_TOKENS:
        base += low.count(token)
    # normalize to an approximate 0-20 scale
    return min(20.0, base / 6.0)


def _count_unsupported_patterns(text: str) -> int:
    low = (text or "").lower()
    return sum(low.count(tok) for tok in _UNSUPPORTED_TOKENS)


def _iter_code_files(root: Path) -> List[Path]:
    if not root.exists() or not root.is_dir():
        return []
    return [p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in _CODE_EXTENSIONS]


def _build_file_data_from_migrated_code(migrated_code_dir: Path) -> Tuple[List[Dict[str, Any]], Dict[str, float], Dict[str, int]]:
    file_data: List[Dict[str, Any]] = []
    complexity_map: Dict[str, float] = {}
    unsupported_map: Dict[str, int] = {}

    for f in _iter_code_files(migrated_code_dir):
        try:
            text = f.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            text = ""
        loc = len([ln for ln in text.splitlines() if ln.strip()])
        functions = _count_with_patterns(text, _FUNC_PATTERNS)
        imports = _count_with_patterns(text, _IMPORT_PATTERNS)
        complexity = _estimate_complexity_score(text)
        unsupported = _count_unsupported_patterns(text)
        path_str = str(f)
        complexity_map[path_str] = complexity
        unsupported_map[path_str] = unsupported
        file_data.append(
            {
                "fileName": f.name,
                "filePath": path_str,
                "lineOfCode": loc,
                "functionCount": functions,
                "dependencies_libraries": [f"imports:{imports}"],
            }
        )
    return file_data, complexity_map, unsupported_map


def _load_response_from_db_fallback(response_file: Path) -> Dict[str, Any]:
    # file-only for now; placeholder for DB fallback if needed.
    return _safe_read_json(response_file)


def _count_pattern_shifts(mapping: List[Dict[str, Any]]) -> Dict[str, int]:
    shifts: Dict[str, int] = {}
    for m in mapping:
        src = Path(str(m.get("sourcepath") or ""))
        tgt = Path(str(m.get("matched_target_path") or ""))
        if not src.suffix and not tgt.suffix:
            continue
        key = f"{(src.suffix.lower() or '[none]')} -> {(tgt.suffix.lower() or '[none]')}"
        shifts[key] = shifts.get(key, 0) + 1
    return shifts


def _to_markdown(report: Dict[str, Any]) -> str:
    lines: List[str] = []
    lines.append(f"# Migration Risk Report: {report.get('migration_name', '')}")
    lines.append("")
    lines.append("## Risk Heatmap")
    lines.append("")
    lines.append("| Module | Risk Score | Reason | Recommended Action |")
    lines.append("| --- | ---: | --- | --- |")
    for row in report.get("risk_heatmap", []):
        lines.append(
            f"| {row.get('module')} | {row.get('risk_level')} ({row.get('risk_score')}) | "
            f"{row.get('reason')} | {row.get('recommended_action')} |"
        )
    lines.append("")

    lines.append("## Gap Detection")
    lines.append("")
    lines.append("| Gap Type | Location | Severity | Description | Suggested Action |")
    lines.append("| --- | --- | --- | --- | --- |")
    for gap in report.get("gap_detection", []):
        lines.append(
            f"| {gap.get('gap_type')} | {gap.get('location')} | {gap.get('severity')} | "
            f"{gap.get('description')} | {gap.get('suggested_action')} |"
        )
    lines.append("")

    lines.append("## Confidence Score")
    lines.append("")
    lines.append("| Module | Confidence | Meaning |")
    lines.append("| --- | ---: | --- |")
    for row in report.get("confidence_score", []):
        lines.append(
            f"| {row.get('module')} | {row.get('confidence')} | {row.get('meaning')} |"
        )
    lines.append("")
    return "\n".join(lines)


def _persist_report(report: Dict[str, Any], migration_dir: Path, markdown_text: str) -> Dict[str, str]:
    report_dir = migration_dir / "reporting"
    report_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    json_path = report_dir / f"migration_risk_report_{ts}.json"
    md_path = report_dir / f"migration_risk_report_{ts}.md"
    latest_json_path = report_dir / "migration_risk_report_latest.json"
    latest_md_path = report_dir / "migration_risk_report_latest.md"

    json_payload = json.dumps(report, indent=2, ensure_ascii=False)
    json_path.write_text(json_payload, encoding="utf-8")
    md_path.write_text(markdown_text, encoding="utf-8")
    latest_json_path.write_text(json_payload, encoding="utf-8")
    latest_md_path.write_text(markdown_text, encoding="utf-8")

    temp_root = Path(PathConstants.TEMP_DIR).resolve()
    server_base = (os.getenv("SERVER_BASE_URL") or "").strip().strip('"').strip("'").rstrip("/")
    def _relative_under_temp(path: Path) -> str | None:
        # Primary path resolution: relative to configured Temp root.
        try:
            rel = path.resolve().relative_to(temp_root)
            return str(rel).replace("\\", "/")
        except Exception:
            pass
        
        # Fallback for mixed cwd/runtime layouts: cut everything up to ".../Temp/".
        abs_str = str(path.resolve())
        m = re.search(r"(?i)[\\/]+temp[\\/]+(.+)$", abs_str)
        if m:
            return m.group(1).replace("\\", "/")

        parts = list(path.resolve().parts)
        lowered = [p.lower() for p in parts]
        temp_idx = -1
        for i, p in enumerate(lowered):
            if p == "temp":
                temp_idx = i
        if temp_idx >= 0 and temp_idx + 1 < len(parts):
            return "/".join(parts[temp_idx + 1 :]).replace("\\", "/")
        return None

    def _public_or_local(path: Path) -> str:
        server_base = (os.getenv("SERVER_BASE_URL") or "").strip().strip('"').strip("'").rstrip("/")
        if server_base:
            rel = _relative_under_temp(path)
            if rel:
                return f"{server_base}/{quote(rel)}"
            
        return str(path)

    return {
        "json": _public_or_local(json_path),
        "markdown": _public_or_local(md_path),
        "latest_json": _public_or_local(latest_json_path),
        "latest_markdown": _public_or_local(latest_md_path),
    }


def _readiness_check(migration_dir: Path) -> Dict[str, Any]:
    paths = {
        "source_response": migration_dir / "source_response.json",
        "source_scanner_output": migration_dir / "source_scanner_output.json",
        "target_response": migration_dir / "target_response.json",
        "target_scanner_output": migration_dir / "target_scanner_output.json",
        "migrated_code_dir": migration_dir / "Migrated Code",
    }

    core_required = {"source_scanner_output", "migrated_code_dir"}
    optional_target = {"target_response", "target_scanner_output"}

    missing_core: List[str] = []
    missing_optional: List[str] = []
    for key, path in paths.items():
        exists = True
        if key == "migrated_code_dir":
            if not path.exists() or not path.is_dir():
                exists = False
        elif not path.exists():
            exists = False

        if not exists:
            if key in core_required:
                missing_core.append(key)
            elif key in optional_target:
                missing_optional.append(key)

    return {
        "ready_core": len(missing_core) == 0,
        "has_migrated_code": (paths["migrated_code_dir"].exists() and paths["migrated_code_dir"].is_dir()),
        "has_source_response": paths["source_response"].exists(),
        "missing_core": missing_core,
        "missing_optional": missing_optional,
        "required_paths": {k: str(v) for k, v in paths.items()},
    }


def _generate_migrated_only_report(
    migration_name: str,
    migration_dir: Path,
    *,
    persist: bool,
    include_markdown: bool,
) -> Dict[str, Any]:
    migrated_code_dir = migration_dir / "migrated_code"
    file_data, complexity_map, unsupported_map = _build_file_data_from_migrated_code(migrated_code_dir)
    if not file_data:
        return {
            "status": "not_ready",
            "migration_name": migration_name,
            "analysis_mode": "migrated_code_only",
            "message": "No analyzable code files found under migrated_code/",
            "required_paths": {"migrated_code_dir": str(migrated_code_dir)},
        }

    root_path = str(migrated_code_dir)
    modules = _build_module_stats(file_data, root_path)
    by_module: Dict[str, Any] = {}
    gaps: List[Dict[str, Any]] = []

    for module, m in modules.items():
        files = int(m.get("files") or 0)
        loc = int(m.get("loc") or 0)
        funcs = int(m.get("functions") or 0)
        deps = int(m.get("dependencies") or 0)
        paths = m.get("file_paths") or []
        complexity_raw = sum(complexity_map.get(p, 0.0) for p in paths) / max(1, len(paths))
        complexity = _normalize(complexity_raw, 20.0)
        unsupported_raw = sum(unsupported_map.get(p, 0) for p in paths)
        unsupported_score = _normalize(float(unsupported_raw), float(max(1, files * 3)))
        dependency_density = _normalize(float(deps / max(1, files)), 12.0)
        manual_intervention = min(80.0, 20.0 + complexity * 0.35 + unsupported_score * 0.25)
        iterations = 40.0 + (10.0 if complexity >= 60 else 0.0)

        risk_score = round(
            min(
                100.0,
                max(
                    0.0,
                    (0.3 * manual_intervention)
                    + (0.2 * complexity)
                    + (0.2 * iterations)
                    + (0.2 * unsupported_score)
                    + (0.1 * dependency_density),
                ),
            ),
            2,
        )
        risk_level = _risk_label(risk_score)
        confidence = round(max(1.0, min(99.0, 100.0 - risk_score * 0.7)), 2)

        risk_areas: List[str] = []
        if complexity >= 55:
            risk_areas.append("Complex condition rewrites")
        if unsupported_score >= 35:
            risk_areas.append("Potential unsupported legacy patterns")
        if dependency_density >= 55:
            risk_areas.append("High dependency density")
        if not risk_areas:
            risk_areas.append("No major auto-flagged risks")

        by_module[module] = {
            "module": module,
            "risk_score": risk_score,
            "risk_level": risk_level,
            "confidence": confidence,
            "summary": {
                "loc_migrated": loc,
                "auto_conversion_percent": None,
            },
            "what_changed": {
                "legacy_to_modern_pattern": "N/A (source baseline not provided)",
                "key_transformations": [
                    f"Functions detected: {funcs}",
                    f"Files detected: {files}",
                ],
                "semantic_delta": {
                    "function_delta": None,
                    "loc_delta": None,
                    "dependency_delta": None,
                },
                "architectural_shifts": "Migrate-only mode: comparison baseline unavailable",
            },
            "risk_areas": risk_areas,
            "review_checklist": [
                "Validate business logic equivalence against source baseline",
                "Check null/edge case handling",
                "Verify transaction and error handling behavior",
                "Run critical flow integration tests",
            ],
            "reason": "; ".join(risk_areas),
            "metrics": {
                "manual_intervention": round(manual_intervention, 2),
                "complexity": round(complexity, 2),
                "iterations": round(iterations, 2),
                "unsupported_patterns": round(unsupported_score, 2),
                "dependency_density": round(dependency_density, 2),
            },
        }

        if int(m.get("test_files") or 0) == 0:
            gaps.append(
                {
                    "gap_type": "Coverage",
                    "location": module,
                    "severity": "Medium",
                    "description": "No obvious test files detected in migrated module",
                    "suggested_action": "Add/port unit and integration tests",
                }
            )

    ranked = sorted(by_module.values(), key=lambda x: x["risk_score"], reverse=True)
    risk_heatmap = [
        {
            "module": r["module"],
            "risk_score": r["risk_score"],
            "risk_level": f"{_risk_emoji(r['risk_level'])} {r['risk_level']}",
            "reason": r["reason"],
            "recommended_action": (
                "Deep review required"
                if r["risk_level"] == "High"
                else "Focus on edge cases"
                if r["risk_level"] == "Medium"
                else "Spot check only"
            ),
        }
        for r in ranked[:20]
    ]
    confidence_table = [
        {
            "module": r["module"],
            "confidence": f"{r['confidence']}%",
            "meaning": (
                "Needs detailed validation"
                if r["confidence"] < 70
                else "Moderate review"
                if r["confidence"] < 90
                else "Minimal review"
            ),
        }
        for r in ranked
    ]

    report: Dict[str, Any] = {
        "status": "ready",
        "analysis_mode": "migrated_code_only",
        "migration_name": migration_name,
        "report_version": "v3-migrated-only",
        "generated_from": {
            "migrated_code_dir": str(migrated_code_dir),
        },
        "risk_heatmap": risk_heatmap,
        "module_review_cards": ranked,
        "gap_detection": gaps,
        "confidence_score": confidence_table,
        "formula": {
            "risk_score": "(0.3*Manual Intervention) + (0.2*Complexity) + "
            "(0.2*Iterations) + (0.2*Unsupported Patterns) + (0.1*Dependency Density)"
        },
    }

    markdown_text = _to_markdown(report)
    if include_markdown:
        report["markdown_report"] = markdown_text
    if persist:
        report["artifact_paths"] = _persist_report(report, migration_dir, markdown_text)
    return report


def _build_target_side_from_migrated(
    migration_dir: Path,
    target_response: Dict[str, Any],
) -> Tuple[List[Dict[str, Any]], str]:
    """
    Prefer migrated_code as target-side truth for comparison reports.
    Fallback to target_response only when migrated_code is not available.
    """
    migrated_code_dir = migration_dir / "migrated_code"
    if migrated_code_dir.exists() and migrated_code_dir.is_dir():
        file_data, _complexity, _unsupported = _build_file_data_from_migrated_code(migrated_code_dir)
        if file_data:
            return file_data, str(migrated_code_dir)
    target_files = target_response.get("fileData") or []
    target_root = str(target_response.get("src_path") or "")
    return target_files, target_root


def generate_migration_comparison_report(
    migration_name: str,
    *,
    persist: bool = True,
    include_markdown: bool = False,
    require_migrated: bool = True,
) -> Dict[str, Any]:
    migration_dir = get_migration_directory(migration_name=migration_name, source_path="")
    readiness = _readiness_check(migration_dir)
    has_migrated_code = bool(readiness.get("has_migrated_code"))
    # If source baseline artifacts are missing, fall back to migrated-only mode.
    if has_migrated_code and not readiness.get("ready_core"):
        return _generate_migrated_only_report(
            migration_name=migration_name,
            migration_dir=migration_dir,
            persist=persist,
            include_markdown=include_markdown,
        )

    if require_migrated and not has_migrated_code:
        return {
            "status": "not_ready",
            "migration_name": migration_name,
            "message": (
                "Reporting requires migrated_code output. "
                "Run migration/post-migration pipeline first."
            ),
            "missing_prerequisites": readiness.get("missing_core", []),
            "required_paths": readiness["required_paths"],
        }

    source_response = _load_response_from_db_fallback(migration_dir / "source_response.json")
    target_response = _load_response_from_db_fallback(migration_dir / "target_response.json")
    if not source_response.get("fileData"):
        # Scanner v2 may intentionally omit the legacy source_response artifact.
        # Build the minimal comparison baseline directly from the source tree.
        try:
            from app.infrastructure.utils.migration_context import source_path_ctx
            source_root_path = Path(source_path_ctx.get("")) if source_path_ctx.get("") else None
            if source_root_path and source_root_path.exists():
                source_files, _c, _u = _build_file_data_from_migrated_code(source_root_path)
                source_response = {"src_path": str(source_root_path), "fileData": source_files, "nonConvertibleFiles": []}
        except Exception as exc:
            logger.warning("Unable to build source reporting baseline from source tree: %s", exc)
    source_scanner = _safe_read_json(migration_dir / "source_scanner_output.json")
    target_scanner = _safe_read_json(migration_dir / "target_scanner_output.json")
    mapping = _load_mapping(migration_dir)

    source_files = source_response.get("fileData") or []
    target_files, target_root = _build_target_side_from_migrated(
        migration_dir=migration_dir,
        target_response=target_response,
    )
    if not source_files:
        raise ValueError("source_response.json with fileData is required to build report")

    source_root = str(source_response.get("src_path") or "")
    source_modules = _build_module_stats(source_files, source_root)
    target_modules = _build_module_stats(target_files, target_root)

    source_complexity = _map_complexity_by_path(source_scanner.get("complexity_analysis") or [])
    unsupported_files = set(source_response.get("nonConvertibleFiles") or [])

    by_module: Dict[str, Any] = {}
    gap_rows: List[Dict[str, Any]] = []
    pattern_shift_counts = _count_pattern_shifts(mapping)

    manual_ratio_by_module: Dict[str, float] = {}
    if mapping:
        module_total: Dict[str, int] = {}
        module_manual: Dict[str, int] = {}
        for m in mapping:
            src = str(m.get("sourcepath") or "")
            mod = _module_name_from_path(src, source_root)
            module_total[mod] = module_total.get(mod, 0) + 1
            if bool(m.get("needs_conversion")):
                module_manual[mod] = module_manual.get(mod, 0) + 1
        for mod, total in module_total.items():
            manual_ratio_by_module[mod] = (module_manual.get(mod, 0) / total) if total else 0.0

    all_modules = sorted(set(source_modules.keys()) | set(target_modules.keys()))
    for module in all_modules:
        s = source_modules.get(module, {})
        t = target_modules.get(module, {})
        s_files = int(s.get("files") or 0)
        t_files = int(t.get("files") or 0)
        s_func = int(s.get("functions") or 0)
        t_func = int(t.get("functions") or 0)
        s_loc = int(s.get("loc") or 0)
        t_loc = int(t.get("loc") or 0)
        s_deps = int(s.get("dependencies") or 0)

        auto_conversion = 0.0
        if module in manual_ratio_by_module:
            auto_conversion = (1.0 - manual_ratio_by_module[module]) * 100.0
        elif s_files:
            auto_conversion = _normalize(float(min(s_files, t_files)), float(s_files))

        manual_intervention = 100.0 - auto_conversion
        avg_complexity_raw = 0.0
        file_paths = s.get("file_paths") or []
        if file_paths:
            vals = [source_complexity.get(fp, 0.0) for fp in file_paths]
            avg_complexity_raw = sum(vals) / len(vals) if vals else 0.0
        complexity = _normalize(avg_complexity_raw, 20.0)
        unsupported_count = sum(1 for fp in file_paths if fp in unsupported_files)
        unsupported_score = _normalize(float(unsupported_count), float(max(1, s_files)))
        dependency_density_raw = (s_deps / max(1, s_files))
        dependency_density = _normalize(dependency_density_raw, 12.0)
        iterations = 25.0 if auto_conversion >= 85 else 45.0 if auto_conversion >= 60 else 65.0

        risk_score = (
            0.3 * manual_intervention
            + 0.2 * complexity
            + 0.2 * iterations
            + 0.2 * unsupported_score
            + 0.1 * dependency_density
        )
        risk_score = round(min(100.0, max(0.0, risk_score)), 2)
        risk_level = _risk_label(risk_score)

        confidence = round(
            min(
                99.0,
                max(
                    1.0,
                    100.0
                    - risk_score * 0.75
                    + _normalize(float(t.get("test_files") or 0), float(max(1, t_files))) * 0.1,
                ),
            ),
            2,
        )

        reasons = []
        if auto_conversion < 70:
            reasons.append("Low auto-conversion")
        if complexity >= 60:
            reasons.append("High complexity")
        if unsupported_score >= 40:
            reasons.append("Unsupported patterns present")
        if dependency_density >= 60:
            reasons.append("High dependency density")
        if not reasons:
            reasons.append("Mostly auto-converted with manageable complexity")

        risk_areas = []
        if complexity >= 55:
            risk_areas.append("Complex condition rewrites")
            risk_areas.append("Error handling differences")
        if dependency_density >= 55:
            risk_areas.append("DB transaction handling")
        if abs(t_func - s_func) >= 5:
            risk_areas.append("Data transformation inconsistencies")
        if not risk_areas:
            risk_areas.append("No major auto-flagged risks")

        ext_src = ", ".join(sorted((s.get("extensions") or {}).keys())[:4]) or "unknown"
        ext_tgt = ", ".join(sorted((t.get("extensions") or {}).keys())[:4]) or "unknown"
        checklist = [
            "Validate business logic equivalence",
            "Check null/edge case handling",
            "Verify DB transaction consistency",
            "Confirm API contract compatibility",
        ]

        by_module[module] = {
            "module": module,
            "risk_score": risk_score,
            "risk_level": risk_level,
            "confidence": confidence,
            "summary": {
                "loc_migrated": t_loc,
                "auto_conversion_percent": round(auto_conversion, 2),
            },
            "what_changed": {
                "legacy_to_modern_pattern": f"{ext_src} -> {ext_tgt}",
                "key_transformations": [
                    f"Functions: {s_func} (source) vs {t_func} (target)",
                    f"Files: {s_files} (source) vs {t_files} (target)",
                ],
                "semantic_delta": {
                    "function_delta": t_func - s_func,
                    "loc_delta": t_loc - s_loc,
                    "dependency_delta": int(t.get("dependencies") or 0) - s_deps,
                },
                "architectural_shifts": "Detected through file/module and dependency deltas",
            },
            "risk_areas": risk_areas,
            "review_checklist": checklist,
            "reason": "; ".join(reasons),
            "metrics": {
                "manual_intervention": round(manual_intervention, 2),
                "complexity": round(complexity, 2),
                "iterations": round(iterations, 2),
                "unsupported_patterns": round(unsupported_score, 2),
                "dependency_density": round(dependency_density, 2),
            },
        }

        missing_funcs = max(0, s_func - t_func)
        if missing_funcs >= 3:
            gap_rows.append(
                {
                    "gap_type": "Functional",
                    "location": module,
                    "severity": _severity_from_delta(missing_funcs),
                    "description": f"{missing_funcs} potential functions/branches missing after migration",
                    "suggested_action": "Review logic parity and add missing validations/branches",
                }
            )
        if s_files > t_files:
            gap_rows.append(
                {
                    "gap_type": "Structural",
                    "location": module,
                    "severity": _severity_from_delta(s_files - t_files),
                    "description": f"{s_files - t_files} source files not represented in target module",
                    "suggested_action": "Verify file mapping and complete partial conversions",
                }
            )
        if risk_level == "High" and abs(t_func - s_func) >= 5:
            gap_rows.append(
                {
                    "gap_type": "Behavioral",
                    "location": module,
                    "severity": "High",
                    "description": "High-risk module with notable function delta may alter runtime behavior",
                    "suggested_action": "Run module-level integration and timing/error-flow tests",
                }
            )
        if int(t.get("test_files") or 0) == 0:
            gap_rows.append(
                {
                    "gap_type": "Coverage",
                    "location": module,
                    "severity": "Medium",
                    "description": "No obvious test files detected for migrated module",
                    "suggested_action": "Add/port unit and integration tests for critical flows",
                }
            )

    ranked = sorted(by_module.values(), key=lambda x: x["risk_score"], reverse=True)
    risk_heatmap = [
        {
            "module": r["module"],
            "risk_score": r["risk_score"],
            "risk_level": f"{_risk_emoji(r['risk_level'])} {r['risk_level']}",
            "reason": r["reason"],
            "recommended_action": (
                "Deep review required"
                if r["risk_level"] == "High"
                else "Focus on edge cases"
                if r["risk_level"] == "Medium"
                else "Spot check only"
            ),
        }
        for r in ranked[:20]
    ]
    confidence_table = [
        {
            "module": r["module"],
            "confidence": f"{r['confidence']}%",
            "meaning": (
                "Needs detailed validation"
                if r["confidence"] < 70
                else "Moderate review"
                if r["confidence"] < 90
                else "Minimal review"
            ),
        }
        for r in ranked
    ]

    report: Dict[str, Any] = {
        "status": "ready",
        "analysis_mode": "source_vs_migrated",
        "migration_name": migration_name,
        "report_version": "v2",
        "generated_from": {
            "source_response": str(migration_dir / "source_response.json"),
            "source_scanner_output": str(migration_dir / "source_scanner_output.json"),
            "migrated_code_dir": str(migration_dir / "migrated_code"),
            "file_mapping": str(migration_dir / "file_mapping.json"),
            "target_response": str(migration_dir / "target_response.json"),
            "target_scanner_output": str(migration_dir / "target_scanner_output.json"),
            "target_artifacts_optional": True,
            "missing_optional_artifacts": readiness.get("missing_optional", []),
        },
        "conversion_pattern_shifts": pattern_shift_counts,
        "risk_heatmap": risk_heatmap,
        "module_review_cards": ranked,
        "gap_detection": gap_rows,
        "confidence_score": confidence_table,
        "formula": {
            "risk_score": "(0.3*Manual Intervention) + (0.2*Complexity) + "
            "(0.2*Iterations) + (0.2*Unsupported Patterns) + (0.1*Dependency Density)"
        },
    }

    markdown_text = _to_markdown(report)
    if include_markdown:
        report["markdown_report"] = markdown_text
    if persist:
        report["artifact_paths"] = _persist_report(report, migration_dir, markdown_text)
    return report
