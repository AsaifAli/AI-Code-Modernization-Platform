from __future__ import annotations

"""Conservative post-generation import normalization.

Generated symbol code is appended to target files. This pass makes the
language-level invariant explicit: imports/using directives belong in the
file's import section rather than being left between converted symbols.

It intentionally does not attempt semantic import synthesis; it only moves
existing import declarations. A file is changed only when a declaration can
be recognized safely.
"""

import ast
import re
from pathlib import Path
from typing import Any


_IMPORT_PATTERNS = {
    ".js": re.compile(r"^\s*(?:import\s.+?;?|export\s+.*?\s+from\s+['\"].+?['\"];?)\s*$"),
    ".jsx": re.compile(r"^\s*(?:import\s.+?;?|export\s+.*?\s+from\s+['\"].+?['\"];?)\s*$"),
    ".ts": re.compile(r"^\s*(?:import\s.+?;?|export\s+.*?\s+from\s+['\"].+?['\"];?)\s*$"),
    ".tsx": re.compile(r"^\s*(?:import\s.+?;?|export\s+.*?\s+from\s+['\"].+?['\"];?)\s*$"),
    ".java": re.compile(r"^\s*import\s+[\w.*]+\s*;\s*$"),
    ".cs": re.compile(r"^\s*(?:global\s+)?using\s+.+?;\s*$"),
    ".go": re.compile(r"^\s*import(?:\s*\(|\s+['\"].+?['\"])\s*$"),
    ".php": re.compile(r"^\s*use\s+[^;]+;\s*$"),
}


def _python_normalize(path: Path, text: str) -> tuple[str, int]:
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return text, 0

    import_nodes = [n for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom))]
    if not import_nodes:
        return text, 0

    lines = text.splitlines(keepends=True)
    ranges = []
    for node in import_nodes:
        # ast end positions are 1-based
        ranges.append((node.lineno - 1, node.end_lineno))
    import_text = []
    for start, end in ranges:
        import_text.extend(lines[start:end])

    remaining = [
        line for i, line in enumerate(lines)
        if not any(start <= i < end for start, end in ranges)
    ]

    # Preserve shebang and module docstring at the front. Then put imports,
    # followed by the rest of the file. This is safe for normal Python modules.
    prefix = []
    if remaining and remaining[0].startswith("#!"):
        prefix.append(remaining.pop(0))
    # Keep encoding comment directly after shebang if present.
    while remaining and re.match(r"^\s*#.*coding[:=]", remaining[0]):
        prefix.append(remaining.pop(0))

    try:
        rem_tree = ast.parse("".join(remaining))
        body = rem_tree.body
        doc_end = 0
        if body and isinstance(body[0], ast.Expr) and isinstance(getattr(body[0], "value", None), ast.Constant) and isinstance(body[0].value.value, str):
            doc_end = body[0].end_lineno or 0
    except SyntaxError:
        doc_end = 0

    if doc_end:
        prefix.extend(remaining[:doc_end])
        remaining = remaining[doc_end:]

    # Deduplicate exact import blocks while preserving first occurrence.
    seen = set()
    unique_imports = []
    for line in import_text:
        if line not in seen:
            seen.add(line)
            unique_imports.append(line)

    normalized = "".join(prefix + unique_imports)
    if normalized and not normalized.endswith("\n"):
        normalized += "\n"
    normalized += "".join(remaining).lstrip("\n")
    return normalized, len(unique_imports)


def _regex_normalize(path: Path, text: str) -> tuple[str, int]:
    pattern = _IMPORT_PATTERNS.get(path.suffix.lower())
    if not pattern:
        return text, 0

    lines = text.splitlines(keepends=True)
    imports: list[str] = []
    remaining: list[str] = []
    for line in lines:
        if pattern.match(line):
            imports.append(line)
        else:
            remaining.append(line)

    if not imports:
        return text, 0

    # Go and PHP have mandatory package/namespace declarations before imports.
    if path.suffix.lower() == ".go":
        package_idx = next((i for i, line in enumerate(remaining) if re.match(r"^\s*package\s+\w+", line)), -1)
        if package_idx >= 0:
            remaining[package_idx + 1:package_idx + 1] = ["\n"] + imports
        else:
            remaining = imports + remaining
    elif path.suffix.lower() == ".php":
        namespace_idx = next((i for i, line in enumerate(remaining) if re.match(r"^\s*namespace\s+[^;]+;", line)), -1)
        if namespace_idx >= 0:
            remaining[namespace_idx + 1:namespace_idx + 1] = ["\n"] + imports
        else:
            remaining = imports + remaining
    elif path.suffix.lower() == ".java":
        package_idx = next((i for i, line in enumerate(remaining) if re.match(r"^\s*package\s+[^;]+;", line)), -1)
        if package_idx >= 0:
            remaining[package_idx + 1:package_idx + 1] = ["\n"] + imports
        else:
            remaining = imports + remaining
    else:
        remaining = imports + remaining

    normalized = "".join(remaining)
    return normalized, len(imports)


def normalize_imports_in_tree(root: str | Path) -> dict[str, Any]:
    root = Path(root)
    changed: list[str] = []
    skipped: list[str] = []
    moved = 0

    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in _IMPORT_PATTERNS and path.suffix.lower() != ".py":
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            skipped.append(str(path))
            continue

        if path.suffix.lower() == ".py":
            normalized, count = _python_normalize(path, text)
        else:
            normalized, count = _regex_normalize(path, text)

        if normalized != text:
            path.write_text(normalized, encoding="utf-8")
            changed.append(str(path))
            moved += count

    return {
        "status": "completed",
        "files_changed": len(changed),
        "imports_moved_or_deduplicated": moved,
        "changed_files": changed,
        "skipped_files": skipped,
    }
