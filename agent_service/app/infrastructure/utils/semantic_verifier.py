"""Evidence-based semantic/behavioral verification for migrated repositories.

The verifier deliberately separates *contract evidence* from claims of full semantic
 equivalence. It extracts public symbols from source and target, compares normalized
names/signatures where possible, inventories target tests, and optionally executes the
existing target test suite. This gives the migration platform a defensible semantic
verification layer without pretending static analysis proves business equivalence.
"""
from __future__ import annotations

import ast
import json
import re
import subprocess
import time
from collections import Counter
from pathlib import Path
from typing import Any

from app.infrastructure.utils.behavioral_probe_engine import execute_behavioral_probes

IGNORED = {".git", ".venv", "venv", "node_modules", "vendor", "dist", "build", "target", "__pycache__", ".migration", ".pytest_cache"}
EXTENSIONS = {".py", ".js", ".jsx", ".ts", ".tsx", ".java", ".go", ".php", ".cs"}


def _files(root: Path):
    return [p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in EXTENSIONS and not any(x in IGNORED for x in p.relative_to(root).parts)]


def _public_name(name: str) -> bool:
    return not name.startswith("_")


def _norm(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


def _python_symbols(path: Path) -> list[dict[str, Any]]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"))
    except Exception:
        return []
    out = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and _public_name(node.name):
            args = [a.arg for a in node.args.args if a.arg != "self"]
            out.append({"name": node.name, "normalized": _norm(node.name), "kind": "function", "arity": len(args), "line": node.lineno})
        elif isinstance(node, ast.ClassDef) and _public_name(node.name):
            methods = []
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and _public_name(child.name):
                    methods.append({"name": child.name, "normalized": _norm(child.name), "kind": "method", "arity": max(0, len(child.args.args) - 1), "line": child.lineno})
            out.append({"name": node.name, "normalized": _norm(node.name), "kind": "class", "arity": None, "line": node.lineno, "methods": methods})
    return out


def _regex_symbols(path: Path) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    ext = path.suffix.lower()
    patterns = []
    if ext in {".js", ".jsx", ".ts", ".tsx"}:
        patterns = [(r"(?:export\s+)?(?:async\s+)?function\s+([A-Za-z_$][\w$]*)\s*\(([^)]*)\)", "function"),
                    (r"(?:export\s+)?class\s+([A-Za-z_$][\w$]*)", "class"),
                    (r"(?:export\s+)?(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?\(([^)]*)\)\s*=>", "function")]
    elif ext == ".java":
        patterns = [(r"(?:public|protected)\s+(?:static\s+)?[\w<>\[\], ?]+\s+([A-Za-z_]\w*)\s*\(([^)]*)\)", "method"),
                    (r"(?:public|protected)\s+(?:abstract\s+)?class\s+([A-Za-z_]\w*)", "class")]
    elif ext == ".go":
        patterns = [(r"func\s+([A-Za-z_]\w*)\s*\(([^)]*)\)", "function"), (r"type\s+([A-Za-z_]\w*)\s+struct", "class")]
    elif ext == ".php":
        patterns = [(r"function\s+([A-Za-z_]\w*)\s*\(([^)]*)\)", "function"), (r"class\s+([A-Za-z_]\w*)", "class")]
    elif ext == ".cs":
        patterns = [(r"(?:public|protected|internal)\s+(?:static\s+)?[\w<>\[\], ?]+\s+([A-Za-z_]\w*)\s*\(([^)]*)\)", "method"),
                    (r"(?:public|internal)\s+class\s+([A-Za-z_]\w*)", "class")]
    out = []
    for pat, kind in patterns:
        for m in re.finditer(pat, text):
            name = m.group(1)
            args = m.group(2) if m.lastindex and m.lastindex >= 2 else ""
            arity = 0 if not args.strip() else len([x for x in args.split(",") if x.strip()])
            if _public_name(name):
                out.append({"name": name, "normalized": _norm(name), "kind": kind, "arity": arity, "line": text.count("\n", 0, m.start()) + 1})
    return out


def extract_symbols(root: str | Path) -> list[dict[str, Any]]:
    root = Path(root).resolve()
    symbols = []
    for path in _files(root):
        rel = str(path.relative_to(root))
        parsed = _python_symbols(path) if path.suffix.lower() == ".py" else _regex_symbols(path)
        for symbol in parsed:
            symbol["file"] = rel
            symbols.append(symbol)
    return symbols


def _test_inventory(root: Path) -> dict[str, Any]:
    tests = []
    for p in root.rglob("*"):
        if not p.is_file() or any(x in IGNORED for x in p.relative_to(root).parts):
            continue
        n = p.name.lower()
        if n.startswith("test_") or n.endswith("_test.py") or ".test." in n or ".spec." in n or n.endswith("test.go"):
            tests.append(str(p.relative_to(root)))
    return {"files": sorted(tests), "count": len(tests)}


def _match(source: list[dict[str, Any]], target: list[dict[str, Any]]) -> tuple[list[dict], list[dict]]:
    buckets: dict[str, list[dict]] = {}
    for t in target:
        buckets.setdefault(t["normalized"], []).append(t)
    matches, missing = [], []
    for s in source:
        candidates = buckets.get(s["normalized"], [])
        if not candidates:
            missing.append(s)
            continue
        t = candidates.pop(0)
        arity_ok = s.get("arity") is None or t.get("arity") is None or s.get("arity") == t.get("arity")
        matches.append({"source": s, "target": t, "arity_compatible": arity_ok})
    return matches, missing


def _execute_target_tests(root: Path, timeout: int = 300) -> dict[str, Any]:
    commands = []
    if (root / "pyproject.toml").exists() or any(root.rglob("*.py")):
        commands.append(["python", "-m", "pytest", "-q"])
    elif (root / "package.json").exists():
        commands.append(["npm", "test", "--", "--runInBand"])
    elif (root / "go.mod").exists():
        commands.append(["go", "test", "./..."])
    else:
        return {"status": "not_applicable", "reason": "No supported test runner detected."}
    command = commands[0]
    started = time.monotonic()
    try:
        proc = subprocess.run(command, cwd=root, text=True, capture_output=True, timeout=timeout, env={"CI": "1", **__import__("os").environ})
        return {"status": "passed" if proc.returncode == 0 else "failed", "command": command, "return_code": proc.returncode,
                "duration_seconds": round(time.monotonic() - started, 3), "stdout": proc.stdout[-8000:], "stderr": proc.stderr[-8000:]}
    except FileNotFoundError:
        return {"status": "unavailable", "command": command, "reason": f"Executable '{command[0]}' is not installed."}
    except subprocess.TimeoutExpired:
        return {"status": "failed", "command": command, "return_code": 124, "reason": "Test execution timed out."}


def verify_migration_semantics(source_root: str | Path | None, target_root: str | Path, migration_name: str = "", persist: bool = True) -> dict[str, Any]:
    target = Path(target_root).resolve()
    source = Path(source_root).resolve() if source_root else None
    source_symbols = extract_symbols(source) if source and source.exists() and source.is_dir() else []
    target_symbols = extract_symbols(target)
    matches, missing = _match(source_symbols, target_symbols) if source_symbols else ([], [])
    incompatible = [m for m in matches if not m["arity_compatible"]]
    tests = _test_inventory(target)
    execution = _execute_target_tests(target) if tests["count"] else {"status": "not_run", "reason": "No target tests discovered."}
    probes = execute_behavioral_probes(source, target, matches) if source and source.exists() else {"status": "not_available", "reason": "Source project is unavailable."}

    source_count = len(source_symbols)
    matched_count = len(matches)
    contract_coverage = round((matched_count / source_count) * 100, 2) if source_count else None
    arity_coverage = round(((matched_count - len(incompatible)) / matched_count) * 100, 2) if matched_count else None
    score_parts = []
    if contract_coverage is not None: score_parts.append(contract_coverage)
    if arity_coverage is not None: score_parts.append(arity_coverage)
    if execution["status"] == "passed": score_parts.append(100.0)
    elif execution["status"] == "failed": score_parts.append(0.0)
    if probes["status"] == "passed": score_parts.append(probes.get("coverage_percent", 0.0))
    elif probes["status"] == "failed": score_parts.append(0.0)
    score = round(sum(score_parts) / len(score_parts), 2) if score_parts else None
    status = "verified" if (source_count and not missing and not incompatible and execution.get("status") in {"passed", "not_run"} and probes.get("status") in {"passed", "not_available"}) else ("partial" if source_count else "not_available")

    result = {
        "status": status, "migration_name": migration_name, "source_path": str(source) if source else None,
        "target_path": str(target), "score": score,
        "contract": {"source_symbols": source_count, "target_symbols": len(target_symbols), "matched": matched_count,
                     "missing": len(missing), "arity_incompatible": len(incompatible), "coverage_percent": contract_coverage,
                     "arity_compatibility_percent": arity_coverage, "missing_symbols": missing[:100], "incompatible": incompatible[:100], "matched_symbols": matches[:250]},
        "test_evidence": tests, "execution": execution, "behavioral_probes": probes,
        "limitations": [
            "Contract matching is evidence, not proof of semantic equivalence.",
            "Names are normalized across languages; renamed symbols require explicit mapping metadata for stronger matching.",
            "Existing target tests provide execution evidence; generated tests are not treated as authoritative until they pass independently.",
            "Behavioral probes are limited to conservative, side-effect-light functions with JSON-serializable inputs; unavailable runtimes are reported rather than inferred.",
        ],
    }
    if persist:
        out = target / ".migration"; out.mkdir(exist_ok=True)
        (out / "semantic_verification.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        md = ["# Semantic & Behavioral Verification", "", f"- **Status:** {status}", f"- **Score:** {score if score is not None else 'N/A'}/100", "",
              "## Contract Evidence", "", f"- Source public symbols: {source_count}", f"- Target symbols: {len(target_symbols)}", f"- Matched: {matched_count}",
              f"- Missing: {len(missing)}", f"- Arity incompatible: {len(incompatible)}", f"- Contract coverage: {contract_coverage if contract_coverage is not None else 'N/A'}%", "",
              "## Test Evidence", "", f"- Discovered test files: {tests['count']}", f"- Execution: {execution.get('status')}", "", "## Behavioral Probes", "", f"- Status: {probes.get('status')}", f"- Selected functions: {probes.get('selected', 0)}", f"- Cases: {probes.get('cases', 0)}", f"- Passed: {probes.get('passed', 0)}", f"- Failed: {probes.get('failed', 0)}", f"- Coverage: {probes.get('coverage_percent', 0)}%", "", "## Limitations", ""]
        md += [f"- {x}" for x in result["limitations"]]
        (out / "semantic_verification.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    return result
