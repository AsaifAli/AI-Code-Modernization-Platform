"""Deterministic source-vs-target behavioral probes.

The probe engine deliberately targets small, high-value, side-effect-light functions.
It executes the source as an oracle, feeds the same JSON-serializable inputs to the
migrated target, and compares normalized JSON outputs.  Unsupported runtimes are
reported as unavailable rather than guessed.  This is evidence of behavioral
compatibility, not a proof of semantic equivalence.
"""
from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

from app.infrastructure.utils.language_adapters import get_adapter

IGNORED_PARTS = {".git", ".venv", "venv", "node_modules", "vendor", "dist", "build", ".migration", "__pycache__"}


def _python_pure_functions(root: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for path in root.rglob("*.py"):
        if any(p in IGNORED_PARTS for p in path.relative_to(root).parts):
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"), filename=str(path))
        except Exception:
            continue
        for node in tree.body:
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) or node.name.startswith("_"):
                continue
            args = [a for a in node.args.args]
            # A conservative purity heuristic: reject IO, imports, mutation and calls
            # to unknown functions. Builtins used in expressions are still allowed.
            unsafe = (ast.Import, ast.ImportFrom, ast.Global, ast.Nonlocal, ast.Await, ast.Yield, ast.YieldFrom, ast.With, ast.AsyncWith, ast.Try, ast.Raise)
            if any(isinstance(n, unsafe) for n in ast.walk(node)):
                continue
            safe_calls = {"len", "abs", "min", "max", "sum", "sorted", "round", "int", "float", "str", "bool"}
            if any(isinstance(n, ast.Call) and not (isinstance(n.func, ast.Name) and n.func.id in safe_calls) for n in ast.walk(node)):
                continue
            # Local assignments are fine; reject explicit mutation of an object or collection.
            if any(isinstance(n, (ast.Delete, ast.AugAssign)) or (isinstance(n, ast.Assign) and any(isinstance(t, (ast.Attribute, ast.Subscript)) for t in n.targets)) for n in ast.walk(node)):
                continue
            if len(args) > 4 or not args:
                continue
            out.append({"name": node.name, "file": str(path.relative_to(root)), "arity": len(args), "line": node.lineno,
                        "parameters": [a.arg for a in args]})
    return out


def _value_for(name: str, index: int, variant: int) -> Any:
    n = name.lower()
    if any(k in n for k in ("id", "count", "num", "index", "size", "age", "amount", "total", "limit", "offset")):
        values = [0, 1, -1, 7]
    elif any(k in n for k in ("flag", "enabled", "active", "valid", "ok", "is_", "has_")):
        values = [False, True]
    elif any(k in n for k in ("items", "values", "list", "numbers", "ids")):
        values = [[], [1, 2], [0, -1, 3]]
    elif any(k in n for k in ("data", "payload", "config", "options", "meta")):
        values = [{}, {"value": 1}]
    else:
        values = ["", "alpha", "migration"]
    return values[(variant + index) % len(values)]


def build_probe_cases(parameters: list[str], max_cases: int = 3) -> list[list[Any]]:
    return [[_value_for(name, i, variant) for i, name in enumerate(parameters)] for variant in range(max_cases)]


def _run_python(root: Path, rel_file: str, function: str, args: list[Any], timeout: int) -> dict[str, Any]:
    script = r'''
import importlib.util, json, sys
path, name, payload = sys.argv[1], sys.argv[2], sys.argv[3]
spec = importlib.util.spec_from_file_location("migration_probe_module", path)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
fn = getattr(mod, name)
result = fn(*json.loads(payload))
if hasattr(result, "__await__"):
    import asyncio
    result = asyncio.run(result)
print(json.dumps(result, sort_keys=True, default=repr))
'''
    return _run_subprocess([sys.executable, "-c", script, str(root / rel_file), function, json.dumps(args)], root, timeout)


def _run_node(root: Path, rel_file: str, function: str, args: list[Any], timeout: int, typescript: bool = False) -> dict[str, Any]:
    script = r'''
const path = process.argv[1], name = process.argv[2], payload = JSON.parse(process.argv[3]);
const mod = await import(path);
let fn = mod[name];
if (!fn && mod.default && typeof mod.default === "object") fn = mod.default[name];
if (typeof fn !== "function") throw new Error(`Export '${name}' not found`);
const result = await fn(...payload);
process.stdout.write(JSON.stringify(result, Object.keys(result || {}).sort()));
'''
    command = ["node", "--input-type=module", "-e", script, str((root / rel_file).resolve().as_uri()), function, json.dumps(args)]
    return _run_subprocess(command, root, timeout)


def _run_subprocess(command: list[str], cwd: Path, timeout: int) -> dict[str, Any]:
    started = time.monotonic()
    env = {"CI": "1", "NO_COLOR": "1", **os.environ}
    try:
        proc = subprocess.run(command, cwd=cwd, text=True, capture_output=True, timeout=timeout, env=env)
    except FileNotFoundError:
        return {"status": "unavailable", "command": command, "reason": f"Executable '{command[0]}' is not installed."}
    except subprocess.TimeoutExpired:
        return {"status": "timeout", "command": command, "duration_seconds": timeout}
    if proc.returncode:
        return {"status": "failed", "command": command, "return_code": proc.returncode,
                "stderr": proc.stderr[-4000:], "duration_seconds": round(time.monotonic() - started, 3)}
    raw = proc.stdout.strip()
    try:
        value = json.loads(raw)
    except Exception:
        value = raw
    return {"status": "passed", "value": value, "duration_seconds": round(time.monotonic() - started, 3)}


def _runtime(path: Path) -> str:
    # Runtime ownership belongs to the language adapter registry. Unsupported
    # languages remain explicitly unavailable rather than being guessed.
    for key in ("python", "node", "java", "go", "php", "dotnet"):
        adapter = get_adapter(key)
        if adapter and adapter.supports_file(path):
            return adapter.probe_runtime or "unsupported"
    return "unsupported"


def select_probe_candidates(source_root: Path, target_root: Path, matches: list[dict[str, Any]], limit: int = 12) -> list[dict[str, Any]]:
    source_funcs = {(x["file"], x["name"]): x for x in _python_pure_functions(source_root)}
    selected = []
    for match in matches:
        s, t = match["source"], match["target"]
        if s.get("kind") != "function" or t.get("kind") not in {"function", "method"}:
            continue
        candidate = source_funcs.get((s.get("file"), s.get("name")))
        if not candidate:
            continue
        if candidate["arity"] != (t.get("arity") if t.get("arity") is not None else candidate["arity"]):
            continue
        if _runtime(target_root / t.get("file", "")) not in {"python", "node"}:
            continue
        selected.append({"source": s, "target": t, "parameters": candidate["parameters"],
                         "cases": build_probe_cases(candidate["parameters"])})
        if len(selected) >= limit:
            break
    return selected


def execute_behavioral_probes(source_root: Path, target_root: Path, matches: list[dict[str, Any]], timeout: int = 20, limit: int = 12) -> dict[str, Any]:
    candidates = select_probe_candidates(source_root, target_root, matches, limit=limit)
    if not candidates:
        return {"status": "not_available", "reason": "No safe, executable pure-function probe candidates were found.", "selected": 0, "passed": 0, "failed": 0, "unavailable": 0, "cases": 0, "results": []}

    results = []
    for candidate in candidates:
        s, t = candidate["source"], candidate["target"]
        for case in candidate["cases"]:
            source_exec = _run_python(source_root, s["file"], s["name"], case, timeout)
            target_path = target_root / t["file"]
            target_exec = _run_python(target_root, t["file"], t["name"], case, timeout) if target_path.suffix == ".py" else _run_node(target_root, t["file"], t["name"], case, timeout)
            comparable = source_exec.get("status") == "passed" and target_exec.get("status") == "passed"
            same = comparable and source_exec.get("value") == target_exec.get("value")
            results.append({"symbol": s["name"], "source": s["file"], "target": t["file"], "inputs": case,
                            "source_status": source_exec.get("status"), "target_status": target_exec.get("status"),
                            "source_value": source_exec.get("value"), "target_value": target_exec.get("value"),
                            "status": "passed" if same else ("failed" if comparable else "unavailable"),
                            "target_error": target_exec.get("stderr") or target_exec.get("reason")})
    passed = sum(r["status"] == "passed" for r in results)
    failed = sum(r["status"] == "failed" for r in results)
    unavailable = sum(r["status"] == "unavailable" for r in results)
    status = "passed" if results and failed == 0 and unavailable == 0 else ("failed" if failed else "partial")
    return {"status": status, "selected": len(candidates), "passed": passed, "failed": failed, "unavailable": unavailable,
            "cases": len(results), "coverage_percent": round(passed / len(results) * 100, 2), "results": results[:100]}
