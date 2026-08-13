"""Post-migration architecture intelligence.

Builds a deterministic, language-aware architecture snapshot from the migrated
repository. It intentionally avoids claiming semantic understanding where a
static signal is unavailable; the UI can present this alongside the AI report.
"""
from __future__ import annotations

import ast
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

IGNORED = {".git", ".venv", "venv", "node_modules", "dist", "build", "__pycache__", ".migration", ".pytest_cache"}
EXT_LANG = {
    ".py": "Python", ".js": "JavaScript", ".jsx": "JavaScript", ".ts": "TypeScript", ".tsx": "TypeScript",
    ".java": "Java", ".go": "Go", ".cs": "C#", ".php": "PHP", ".rs": "Rust", ".kt": "Kotlin",
}


def _files(root: Path) -> list[Path]:
    return [p for p in root.rglob("*") if p.is_file() and not any(part in IGNORED for part in p.parts)]


def _imports(path: Path, root: Path) -> list[str]:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return []
    if path.suffix == ".py":
        try:
            tree = ast.parse(text)
            out = []
            for n in ast.walk(tree):
                if isinstance(n, ast.Import):
                    out.extend(a.name.split(".")[0] for a in n.names)
                elif isinstance(n, ast.ImportFrom) and n.module:
                    out.append(n.module.split(".")[0])
            return out[:30]
        except SyntaxError:
            return []
    if path.suffix in {".js", ".jsx", ".ts", ".tsx"}:
        return re.findall(r"(?:from\s+|require\()\s*['\"]([^'\"]+)", text)[:30]
    if path.suffix == ".java":
        return re.findall(r"^import\s+([\w.]+);", text, re.M)[:30]
    if path.suffix == ".go":
        return re.findall(r'"([^\"]+)"', re.search(r"import\s*\((.*?)\)", text, re.S).group(1))[:30] if re.search(r"import\s*\((.*?)\)", text, re.S) else []
    if path.suffix == ".php":
        return re.findall(r"(?:use|require|include)\s+[(']?([\\\w./-]+)", text)[:30]
    return []


def analyze_migrated_architecture(root: str | Path, migration_name: str = "", persist: bool = True) -> dict[str, Any]:
    root = Path(root).resolve()
    files = _files(root)
    languages = Counter(EXT_LANG.get(p.suffix.lower(), "Other") for p in files)
    top_dirs = Counter((p.relative_to(root).parts[0] if len(p.relative_to(root).parts) > 1 else "root") for p in files)
    ext_counts = Counter(p.suffix.lower() or "[no extension]" for p in files)

    nodes: dict[str, dict[str, Any]] = {}
    edges: set[tuple[str, str]] = set()
    file_nodes: dict[Path, str] = {}
    for p in files:
        parts = p.relative_to(root).parts
        node = parts[0] if len(parts) > 1 else p.name
        file_nodes[p] = node
        nodes.setdefault(node, {"name": node, "files": 0, "kind": "directory" if len(parts) > 1 else "file"})["files"] += 1
    known_nodes = set(nodes)
    for p in files:
        node = file_nodes[p]
        for imp in _imports(p, root):
            target = imp.split("/")[0].split(".")[0]
            if target in known_nodes and target != node:
                edges.add((node, target))

    # Add architectural layers inferred from conventional directory names.
    layer_map = {
        "presentation": "Presentation / API", "api": "Presentation / API", "routes": "Presentation / API",
        "controllers": "Presentation / API", "ui": "Presentation / UI", "frontend": "Presentation / UI",
        "application": "Application / Use Cases", "services": "Application / Services",
        "domain": "Domain", "models": "Domain / Models", "entities": "Domain / Models",
        "infrastructure": "Infrastructure", "repositories": "Infrastructure / Data Access", "repository": "Infrastructure / Data Access",
        "data": "Infrastructure / Data", "db": "Infrastructure / Data", "database": "Infrastructure / Data",
        "tests": "Verification", "test": "Verification", "docs": "Documentation",
    }
    layers = defaultdict(list)
    for n in nodes:
        layers[layer_map.get(n.lower(), "Application / Modules")].append(n)

    mermaid = ["flowchart LR"]
    mermaid.append('  classDef layer fill:#eef2ff,stroke:#6366f1,stroke-width:1px;')
    for i, (layer, members) in enumerate(layers.items()):
        lid = f"L{i}"
        mermaid.append(f'  subgraph {lid}["{layer}"]')
        for m in sorted(members):
            safe = re.sub(r"[^A-Za-z0-9_]", "_", m)[:40]
            mermaid.append(f'    {safe}["{m}<br/>{nodes[m]["files"]} files"]')
        mermaid.append("  end")
    for a, b in sorted(edges):
        sa = re.sub(r"[^A-Za-z0-9_]", "_", a)[:40]
        sb = re.sub(r"[^A-Za-z0-9_]", "_", b)[:40]
        mermaid.append(f"  {sa} --> {sb}")

    largest = sorted(((str(p.relative_to(root)), p.stat().st_size) for p in files), key=lambda x: x[1], reverse=True)[:10]
    architecture_style = "layered / modular" if any(k in layers for k in ("Presentation / API", "Application / Use Cases", "Infrastructure", "Domain")) else "modular repository"
    analysis = {
        "migration_name": migration_name,
        "generated_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
        "project_path": str(root),
        "architecture_style": architecture_style,
        "summary": f"The migrated repository contains {len(files)} source/config files across {len(nodes)} top-level modules. Static signals suggest a {architecture_style} structure.",
        "file_count": len(files),
        "languages": dict(languages),
        "extensions": dict(ext_counts),
        "modules": [nodes[k] for k in sorted(nodes)],
        "layers": {k: sorted(v) for k, v in layers.items()},
        "dependency_edges": [{"from": a, "to": b} for a, b in sorted(edges)],
        "largest_files": [{"file": p, "bytes": s} for p, s in largest],
        "diagram_mermaid": "\n".join(mermaid),
        "limitations": [
            "Architecture is inferred from repository structure and import/include signals.",
            "External package dependencies are represented as import signals, not runtime call graphs.",
            "Use the AI migration report for semantic/business-logic interpretation.",
        ],
    }
    if persist:
        out = root / ".migration"
        out.mkdir(exist_ok=True)
        (out / "architecture_analysis.json").write_text(json.dumps(analysis, indent=2), encoding="utf-8")
        md = ["# Migrated Code Architecture Analysis", "", f"## Executive Summary\n{analysis['summary']}", "", "## Architecture Diagram", "", "```mermaid", analysis["diagram_mermaid"], "```", "", "## Technology Profile", ""]
        for lang, count in sorted(languages.items(), key=lambda x: (-x[1], x[0])):
            md.append(f"- **{lang}:** {count} files")
        md += ["", "## Modules", ""]
        for module in sorted(nodes.values(), key=lambda x: x["name"]):
            md.append(f"- **{module['name']}** — {module['files']} files")
        md += ["", "## Architectural Interpretation", "", f"The static structure most closely resembles a **{architecture_style}** repository.", ""]
        md += ["## Important Limitations", ""] + [f"- {x}" for x in analysis["limitations"]]
        (out / "architecture_analysis.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    return analysis
