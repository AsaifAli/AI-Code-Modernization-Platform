from app.infrastructure.utils.symbol_split_policy import (
    HARD_MAX_LOC,
    build_relationship_index,
    relationship_metrics,
    policy_for_symbol,
)


def _sym(sid, start, end, deps=None, complexity=1):
    return {
        "symbol_id": sid,
        "meta_data": {
            "line_range": {"start": start, "end": end},
            "dependencies": [
                {"target": d, "resolved": True} for d in (deps or [])
            ],
            "complexity": complexity,
        },
    }


def test_relationships_capture_many_to_one_and_one_to_many():
    symbols = [
        _sym("a", 1, 10, ["shared"]),
        _sym("b", 1, 10, ["shared"]),
        _sym("shared", 1, 20),
    ]
    graph = build_relationship_index(symbols)
    metrics = relationship_metrics(graph)
    assert metrics["shared"]["fan_in"] == 2
    assert metrics["a"]["fan_out"] == 1


def test_hard_loc_split_is_preserved():
    sym = _sym("large", 1, HARD_MAX_LOC + 1)
    policy = policy_for_symbol(sym, relationship_metrics({"large": set()}))
    assert policy["action"] == "split"
    assert policy["risk"]["hard_split"] is True


def test_complexity_can_trigger_review_without_loc_split():
    sym = _sym("complex", 1, 30, complexity=16)
    policy = policy_for_symbol(sym, relationship_metrics({"complex": set()}))
    assert policy["action"] == "review-or-split"
    assert policy["risk"]["high_complexity"] is True


def test_high_fan_in_is_shared_dependency_signal():
    graph = {f"caller_{i}": {"shared"} for i in range(11)}
    graph["shared"] = set()
    metrics = relationship_metrics(graph)
    assert metrics["shared"]["fan_in"] == 11
    assert metrics["shared"]["is_shared_dependency"] == 1
