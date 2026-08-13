from __future__ import annotations

"""Build an auditable symbol dependency/cardinality report from the AST artifact."""

import json
from pathlib import Path
from typing import Any


def build_dependency_topology_report(
    ast_path: str | Path,
    output_path: str | Path | None = None,
) -> dict[str, Any]:
    ast_path = Path(ast_path)
    if not ast_path.exists():
        return {"status": "not_available", "reason": f"{ast_path} not found"}

    data = json.loads(ast_path.read_text(encoding="utf-8"))
    graph = (data.get("project_graph") or {}).get("symbols") or []
    ids = {s.get("symbol_id") for s in graph if s.get("symbol_id")}

    edges: list[dict[str, str]] = []
    outbound: dict[str, set[str]] = {sid: set() for sid in ids}
    inbound: dict[str, set[str]] = {sid: set() for sid in ids}

    for sym in graph:
        sid = sym.get("symbol_id")
        if not sid:
            continue
        meta = sym.get("meta_data", sym) or {}
        for dep in meta.get("dependencies", []) or []:
            if not isinstance(dep, dict) or not dep.get("resolved"):
                continue
            target = dep.get("target")
            if target not in ids or target == sid:
                continue
            outbound[sid].add(target)
            inbound[target].add(sid)
            edges.append({
                "source": sid,
                "target": target,
                "type": str(dep.get("type") or "dependency"),
            })

    cardinality_counts = {
        "one-to-one": 0,
        "one-to-many": 0,
        "many-to-one": 0,
        "many-to-many": 0,
    }
    for edge in edges:
        src_deg = len(outbound.get(edge["source"], set()))
        tgt_deg = len(inbound.get(edge["target"], set()))
        if src_deg == 1 and tgt_deg == 1:
            kind = "one-to-one"
        elif src_deg == 1 and tgt_deg > 1:
            kind = "one-to-many"
        elif src_deg > 1 and tgt_deg == 1:
            kind = "many-to-one"
        else:
            kind = "many-to-many"
        edge["cardinality"] = kind
        cardinality_counts[kind] += 1

    nodes = []
    for sid in sorted(ids):
        sym = next((s for s in graph if s.get("symbol_id") == sid), {})
        meta = sym.get("meta_data", sym) or {}
        lr = meta.get("line_range") or sym.get("line_range") or {}
        start = int(lr.get("start") or lr.get("start_line") or 0)
        end = int(lr.get("end") or lr.get("end_line") or 0)
        nodes.append({
            "symbol_id": sid,
            "name": sym.get("name") or sym.get("symbol_name") or meta.get("name"),
            "file_path": sym.get("file_path") or meta.get("file_path"),
            "loc": max(0, end - start + 1) if end else int(meta.get("loc") or 0),
            "fan_in": len(inbound.get(sid, set())),
            "fan_out": len(outbound.get(sid, set())),
        })

    report = {
        "status": "completed",
        "method": "AST resolved symbol dependencies",
        "relationship_cardinality": cardinality_counts,
        "nodes": nodes,
        "edges": edges,
        "policy": {
            "hard_split_loc": 150,
            "review_loc": 40,
            "target_part_loc": 80,
            "complexity_review": 10,
            "fan_out_review": 5,
            "fan_in_shared": 10,
            "note": "LOC is a sizing signal; relationship cardinality is derived from the dependency graph.",
        },
    }

    if output_path:
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    return report
