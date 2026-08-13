from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def build_symbol_dependency_graph(*, ast_path: Optional[Path] = None) -> str:
    """
    Build a symbol-level dependency adjacency list and store it in syntactic_ast.json.

    Output shape:
      project_graph.symbol_dependency_graph = { "<symbol_id>": ["<dep_symbol_id>", ...], ... }

    Notes:
    - Uses per-symbol `dependencies` entries when available.
    - Keeps only *internal* symbol dependencies (resolved + target matches a known symbol_id),
      since those are actionable for planning/topological ordering.
    """
    try:
        ast_path = ast_path or (Path("ast_output") / "syntactic_ast.json")
        if not ast_path.exists():
            return f"Error: {ast_path.as_posix()} not found. Run AST generation first."

        with open(ast_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        project_graph = data.get("project_graph", {}) or {}
        symbols = project_graph.get("symbols", []) or []
        symbol_ids = {s.get("symbol_id") for s in symbols if s.get("symbol_id")}

        graph: dict[str, list[str]] = {}

        for sym in symbols:
            sid = sym.get("symbol_id")
            if not sid:
                continue

            deps_out: set[str] = set()
            deps = sym.get("dependencies") or []

            # dependencies in edge form: {source, target, type, resolved}
            if isinstance(deps, list):
                for d in deps:
                    if not isinstance(d, dict):
                        continue
                    if not d.get("resolved", False):
                        continue
                    target = d.get("target")
                    if isinstance(target, str) and target in symbol_ids:
                        deps_out.add(target)

            graph[sid] = sorted(deps_out)

        # Ensure all known symbol_ids exist as keys even if they had no dependencies
        for sid in symbol_ids:
            if sid and sid not in graph:
                graph[sid] = []

        project_graph["symbol_dependency_graph"] = graph
        data["project_graph"] = project_graph

        with open(ast_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        return (
            f"✅ Symbol dependency graph built for {len(graph)} symbols. "
            f"Updated {ast_path.as_posix()}."
        )
    except Exception as e:
        logger.exception("build_symbol_dependency_graph failed")
        return f"Error: {str(e)}"

