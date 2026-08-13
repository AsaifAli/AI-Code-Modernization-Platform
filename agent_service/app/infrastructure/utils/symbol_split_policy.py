from __future__ import annotations

"""
Dependency-aware symbol sizing and split policy.

Important: there is no industry-standard LOC threshold for one-to-many,
many-to-one, or many-to-many relationships. LOC is a size signal, while
relationship cardinality is a graph property. This module deliberately
keeps those concerns separate and combines them into a refactoring signal.

Evidence used by the policy:
- Google Python Style Guide: no hard function-length limit; ~40 LOC is a
  review/refactoring prompt.
- Microsoft/NIST guidance: size should be considered together with
  cyclomatic complexity; complexity >10 is a meaningful warning signal.
- Microsoft Maintainability Index combines LOC, Halstead volume and
  cyclomatic complexity.

The platform keeps 150 LOC as a hard migration split trigger for backward
compatibility, but uses softer targets and graph/complexity signals to decide
HOW to split and whether a symbol should be treated as a shared dependency.
"""

from dataclasses import dataclass, asdict
from typing import Iterable, Mapping, Any


HARD_MAX_LOC = 150
REVIEW_LOC = 40
TARGET_PART_LOC = 80
MIN_PART_LOC = 20
COMPLEXITY_REVIEW = 10
COMPLEXITY_HIGH = 15
FAN_OUT_REVIEW = 5
FAN_OUT_HIGH = 10
FAN_IN_SHARED = 10


@dataclass(frozen=True)
class SymbolRisk:
    loc: int
    complexity: float
    fan_in: int
    fan_out: int
    hard_split: bool
    review_size: bool
    complexity_risk: bool
    high_complexity: bool
    high_fan_out: bool
    shared_dependency: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return default


def _float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return default


def build_relationship_index(symbols: Iterable[Mapping[str, Any]]) -> dict[str, set[str]]:
    """Return source -> resolved target symbol ids."""
    ids = {
        str(s.get("symbol_id"))
        for s in symbols
        if s.get("symbol_id")
    }
    graph: dict[str, set[str]] = {sid: set() for sid in ids}

    for sym in symbols:
        sid = sym.get("symbol_id")
        if not sid:
            continue
        meta = sym.get("meta_data", sym) or {}
        for dep in meta.get("dependencies", []) or []:
            if not isinstance(dep, dict) or not dep.get("resolved"):
                continue
            target = dep.get("target")
            if target in ids and target != sid:
                graph[str(sid)].add(str(target))

        # Calls are a fallback when dependency extraction is incomplete.
        for call in meta.get("calls", []) or []:
            name = call.get("name") if isinstance(call, dict) else str(call)
            if name in ids and name != sid:
                graph[str(sid)].add(str(name))

    return graph


def relationship_metrics(graph: Mapping[str, set[str]]) -> dict[str, dict[str, int]]:
    """Compute fan-in/fan-out and cardinality-oriented metrics."""
    reverse: dict[str, set[str]] = {sid: set() for sid in graph}
    for source, targets in graph.items():
        for target in targets:
            reverse.setdefault(target, set()).add(source)

    result: dict[str, dict[str, int]] = {}
    for sid in set(graph) | set(reverse):
        fan_out = len(graph.get(sid, set()))
        fan_in = len(reverse.get(sid, set()))
        result[sid] = {
            "fan_in": fan_in,
            "fan_out": fan_out,
            "is_shared_dependency": int(fan_in >= FAN_IN_SHARED),
            "is_high_fan_out": int(fan_out > FAN_OUT_HIGH),
            "is_fan_out_review": int(fan_out > FAN_OUT_REVIEW),
        }
    return result


def classify_relationship(source_degree: int, target_degree: int) -> str:
    """
    Classify a directed edge/group relationship.

    This is descriptive, not a splitting threshold:
      1->N = one-to-many
      N->1 = many-to-one
      N->N = many-to-many
      1->1 = one-to-one
    """
    if source_degree == 1 and target_degree == 1:
        return "one-to-one"
    if source_degree == 1 and target_degree > 1:
        return "one-to-many"
    if source_degree > 1 and target_degree == 1:
        return "many-to-one"
    if source_degree > 1 and target_degree > 1:
        return "many-to-many"
    return "unresolved"


def assess_symbol(symbol: Mapping[str, Any], graph_metrics: Mapping[str, Mapping[str, int]] | None = None) -> SymbolRisk:
    meta = symbol.get("meta_data", symbol) or {}
    lr = meta.get("line_range") or symbol.get("line_range") or {}
    start = _int(lr.get("start") or lr.get("start_line"))
    end = _int(lr.get("end") or lr.get("end_line"))
    loc = max(0, end - start + 1) if end else _int(meta.get("loc") or symbol.get("loc"))

    complexity = _float(meta.get("complexity") or symbol.get("complexity"))
    sid = str(symbol.get("symbol_id") or meta.get("symbol_id") or "")
    gm = (graph_metrics or {}).get(sid, {})
    fan_in = _int(gm.get("fan_in"))
    fan_out = _int(gm.get("fan_out"))

    return SymbolRisk(
        loc=loc,
        complexity=complexity,
        fan_in=fan_in,
        fan_out=fan_out,
        hard_split=loc > HARD_MAX_LOC,
        review_size=loc > REVIEW_LOC,
        complexity_risk=complexity > COMPLEXITY_REVIEW,
        high_complexity=complexity > COMPLEXITY_HIGH,
        high_fan_out=fan_out > FAN_OUT_HIGH,
        shared_dependency=fan_in >= FAN_IN_SHARED,
    )


def policy_for_symbol(symbol: Mapping[str, Any], graph_metrics: Mapping[str, Mapping[str, int]] | None = None) -> dict[str, Any]:
    risk = assess_symbol(symbol, graph_metrics)
    meta = symbol.get("meta_data", symbol) or {}
    symbol_type = str(
        symbol.get("symbol_type")
        or meta.get("symbol_type")
        or meta.get("ast_node_type")
        or ""
    ).lower()
    is_test = symbol_type == "test_script"

    if is_test:
        action = "1:1"
        reason = "test symbols remain intact unless the target test framework requires restructuring"
    elif risk.hard_split:
        action = "split"
        reason = "hard LOC guardrail exceeded"
    elif risk.high_complexity or risk.high_fan_out:
        action = "review-or-split"
        reason = "complexity/fan-out indicates elevated maintenance risk"
    elif risk.review_size:
        action = "review"
        reason = "soft size threshold exceeded"
    else:
        action = "1:1"
        reason = "within size and dependency guardrails"

    return {
        "symbol_id": symbol.get("symbol_id"),
        "action": action,
        "reason": reason,
        "risk": risk.to_dict(),
        "guidance": {
            "hard_max_loc": HARD_MAX_LOC,
            "review_loc": REVIEW_LOC,
            "target_part_loc": TARGET_PART_LOC,
            "min_part_loc": MIN_PART_LOC,
            "complexity_review": COMPLEXITY_REVIEW,
            "complexity_high": COMPLEXITY_HIGH,
            "fan_out_review": FAN_OUT_REVIEW,
            "fan_out_high": FAN_OUT_HIGH,
            "fan_in_shared": FAN_IN_SHARED,
        },
    }


def build_split_instructions(symbol: Mapping[str, Any], graph_metrics: Mapping[str, Mapping[str, int]] | None = None) -> str:
    """Create deterministic instructions injected into the LLM planning prompt."""
    p = policy_for_symbol(symbol, graph_metrics)
    r = p["risk"]
    if p["action"] not in {"split", "review-or-split"}:
        return (
            f"Dependency-aware policy: {p['action']} ({p['reason']}). "
            f"Do not split solely because of relationship cardinality."
        )

    relation_note = []
    if r["fan_out"] > FAN_OUT_HIGH:
        relation_note.append("high fan-out: extract cohesive collaborators, but preserve call order and contracts")
    if r["fan_in"] >= FAN_IN_SHARED:
        relation_note.append("high fan-in/shared dependency: prefer keeping a stable public facade and avoid duplicating shared logic")
    if not relation_note:
        relation_note.append("preserve every inbound/outbound dependency explicitly")

    return (
        f"Dependency-aware split policy: {p['reason']}. "
        f"Source LOC={r['loc']}, complexity={r['complexity']}, "
        f"fan-in={r['fan_in']}, fan-out={r['fan_out']}. "
        f"Target part size is approximately {TARGET_PART_LOC} LOC, with "
        f"{MIN_PART_LOC} LOC as a soft minimum; these are review targets, not "
        f"semantic boundaries. " + "; ".join(relation_note) + ". "
        "Split only at AST/logical boundaries (function, method, class, handler, "
        "cohesive helper group). Every dependency used by a part must remain resolvable. "
        "Do not create duplicate imports or duplicate state. If a shared symbol is "
        "referenced by multiple parts, keep one authoritative definition and reference it."
    )
