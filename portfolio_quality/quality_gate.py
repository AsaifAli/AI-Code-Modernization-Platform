"""Dependency-free portfolio quality gate.

Checks the repository for common public-repository mistakes and Python syntax
errors. It intentionally does not import the application, so CI can run it
without a database, LLM, vector store, or model server.
"""
from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path

IGNORED_DIRS = {".git", ".venv", "venv", "__pycache__", ".pytest_cache"}
FORBIDDEN_FILES = {".env"}
FORBIDDEN_SUFFIXES = {".pyc", ".pyo"}
SECRET_PATTERNS = [
    re.compile(r"(?i)\b(?:api[_-]?key|secret[_-]?key|password)\s*=\s*['\"](?!change-me|example|dummy|test)[A-Za-z0-9_\-./+=]{12,}['\"]"),
    re.compile(r"\b(?:10\.\d{1,3}\.\d{1,3}\.\d{1,3}|192\.168\.\d{1,3}\.\d{1,3})\b"),
]


def iter_files(root: Path):
    for path in root.rglob("*"):
        if any(part in IGNORED_DIRS for part in path.parts):
            continue
        if path.is_file():
            yield path


def check_forbidden_files(root: Path) -> list[str]:
    errors = []
    for path in iter_files(root):
        if path.name in FORBIDDEN_FILES or path.suffix in FORBIDDEN_SUFFIXES:
            errors.append(f"forbidden artifact: {path.relative_to(root)}")
    return errors


def check_python_syntax(root: Path) -> list[str]:
    errors = []
    for path in iter_files(root):
        if path.suffix != ".py":
            continue
        try:
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (SyntaxError, UnicodeDecodeError) as exc:
            errors.append(f"python syntax error: {path.relative_to(root)}: {exc}")
    return errors


def check_text_for_secrets(root: Path) -> list[str]:
    errors = []
    allowed_extensions = {".py", ".md", ".yml", ".yaml", ".toml", ".txt", ".json", ".env.example"}
    for path in iter_files(root):
        if path.suffix not in allowed_extensions and path.name != ".gitignore":
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for pattern in SECRET_PATTERNS:
            if pattern.search(text):
                errors.append(f"possible secret/internal address: {path.relative_to(root)}")
                break
    return errors


def run(root: Path) -> dict:
    errors = []
    errors.extend(check_forbidden_files(root))
    errors.extend(check_python_syntax(root))
    errors.extend(check_text_for_secrets(root))
    return {"passed": not errors, "errors": errors}


def main() -> int:
    root = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path.cwd()
    result = run(root)
    print(json.dumps(result, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
