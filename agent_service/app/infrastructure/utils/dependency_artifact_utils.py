"""Deterministic parsing/normalization for generated dependency artifacts."""
import json
import re


def extract_dependency_packages(filename: str, content: str) -> list[str]:
    """Return actual package names from a generated dependency artifact.

    Structured formats are parsed structurally; JSON syntax is never treated as
    a package name. Plain-text dependency files are parsed as requirement lines.
    """
    filename = (filename or "").lower()
    if filename == "package.json":
        try:
            data = json.loads(content) if isinstance(content, str) else content
            if not isinstance(data, dict):
                return []
            packages: set[str] = set()
            for section in (
                "dependencies", "devDependencies",
                "peerDependencies", "optionalDependencies",
            ):
                deps = data.get(section)
                if isinstance(deps, dict):
                    packages.update(str(k).strip() for k in deps if str(k).strip())
            return sorted(packages)
        except (TypeError, json.JSONDecodeError):
            return []

    packages: set[str] = set()
    for line in str(content or "").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        name = re.split(r"(?:===|==|~=|>=|<=|!=|>|<|;|\s+)", line, maxsplit=1)[0].strip()
        if name:
            packages.add(name)
    return sorted(packages)
