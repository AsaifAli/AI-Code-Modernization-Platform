"""Deterministic, model-agnostic migration evaluation harness.

The evaluator intentionally separates structural evidence from behavioral
validation. Structural metrics are always available; an optional test command
can execute a benchmark's target test suite and report its result.

Example:
    python evaluation/evaluate_migration.py \
      --source ./benchmarks/example/source \
      --target ./benchmarks/example/target \
      --test-command "python -m unittest discover -s tests -v" \
      --test-cwd ./benchmarks/example/target
"""
from __future__ import annotations

import argparse
import ast
import json
import shlex
import subprocess
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Sequence

EXCLUDED_DIRS = {".git", "__pycache__", "tests", "test", "__tests__"}


@dataclass
class RepositoryStats:
    files: int
    lines: int
    symbols: int
    python_files: int
    python_syntax_valid: int


def _python_symbols(path: Path) -> int:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (SyntaxError, UnicodeDecodeError, OSError):
        return 0
    return sum(
        isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        for node in ast.walk(tree)
    )


def collect_stats(root: Path) -> RepositoryStats:
    files = [
        p for p in root.rglob("*")
        if p.is_file() and not any(part in EXCLUDED_DIRS for part in p.parts)
    ]
    lines = symbols = py_files = py_valid = 0
    for path in files:
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        lines += len(text.splitlines())
        if path.suffix == ".py":
            py_files += 1
            try:
                ast.parse(text, filename=str(path))
                py_valid += 1
            except SyntaxError:
                pass
            symbols += _python_symbols(path)
    return RepositoryStats(len(files), lines, symbols, py_files, py_valid)


def _relative_files(root: Path) -> set[str]:
    return {
        str(p.relative_to(root))
        for p in root.rglob("*")
        if p.is_file() and not any(part in EXCLUDED_DIRS for part in p.parts)
    }


def run_test_command(command: str, cwd: Path, timeout_seconds: int = 120) -> dict:
    """Run an explicitly supplied benchmark test command with a hard timeout."""
    started = time.perf_counter()
    try:
        completed = subprocess.run(
            shlex.split(command),
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        output = (completed.stdout + "\n" + completed.stderr).strip()
        return {
            "requested": True,
            "passed": completed.returncode == 0,
            "return_code": completed.returncode,
            "duration_ms": duration_ms,
            "command": command,
            "output_tail": output[-4000:],
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "requested": True,
            "passed": False,
            "return_code": None,
            "duration_ms": round((time.perf_counter() - started) * 1000, 2),
            "command": command,
            "output_tail": str(exc)[-4000:],
            "timed_out": True,
        }


def evaluate(
    source: Path,
    target: Path,
    *,
    test_command: str | None = None,
    test_cwd: Path | None = None,
    test_timeout: int = 120,
) -> dict:
    if not source.is_dir():
        raise ValueError(f"Source repository does not exist: {source}")
    if not target.is_dir():
        raise ValueError(f"Target repository does not exist: {target}")

    src = collect_stats(source)
    tgt = collect_stats(target)
    src_files = _relative_files(source)
    tgt_files = _relative_files(target)
    preserved = len(src_files & tgt_files)
    file_coverage = round(100 * preserved / max(1, len(src_files)), 2)
    symbol_coverage = round(100 * tgt.symbols / max(1, src.symbols), 2)
    syntax_validity = round(100 * tgt.python_syntax_valid / max(1, tgt.python_files), 2)

    behavioral = {
        "requested": False,
        "passed": None,
        "return_code": None,
        "duration_ms": None,
        "command": None,
        "output_tail": None,
    }
    if test_command:
        behavioral = run_test_command(test_command, test_cwd or target, test_timeout)

    return {
        "source": asdict(src),
        "target": asdict(tgt),
        "metrics": {
            "relative_file_coverage_percent": file_coverage,
            "python_symbol_ratio_percent": symbol_coverage,
            "python_syntax_validity_percent": syntax_validity,
            "line_delta": tgt.lines - src.lines,
            "file_delta": tgt.files - src.files,
            "symbol_delta": tgt.symbols - src.symbols,
        },
        "behavioral_validation": behavioral,
        "interpretation": [
            "Structural metrics are regression signals, not semantic-equivalence proof.",
            "Behavioral validation is only meaningful when a benchmark test suite is supplied.",
            "Production benchmark evidence should also capture target-language build/lint results and LLM telemetry.",
        ],
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate a source/target migration benchmark")
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--target", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--test-command", help="Optional target test command, e.g. 'python -m unittest discover -s tests'")
    parser.add_argument("--test-cwd", type=Path, help="Working directory for --test-command; defaults to target")
    parser.add_argument("--test-timeout", type=int, default=120)
    args = parser.parse_args(argv)
    result = evaluate(
        args.source,
        args.target,
        test_command=args.test_command,
        test_cwd=args.test_cwd,
        test_timeout=args.test_timeout,
    )
    payload = json.dumps(result, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload + "\n", encoding="utf-8")
    print(payload)
    return 0 if result["behavioral_validation"]["passed"] is not False else 1


if __name__ == "__main__":
    raise SystemExit(main())
