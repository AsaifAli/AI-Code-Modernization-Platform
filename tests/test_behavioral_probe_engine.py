from pathlib import Path

from agent_service.app.infrastructure.utils.behavioral_probe_engine import (
    build_probe_cases,
    execute_behavioral_probes,
    select_probe_candidates,
)


def test_probe_cases_are_json_safe_and_deterministic():
    a = build_probe_cases(["amount", "name"], 3)
    b = build_probe_cases(["amount", "name"], 3)
    assert a == b
    assert a[0] == [0, "alpha"]
    assert a[1] == [1, "migration"]


def test_python_source_to_python_target_behavioral_probe(tmp_path: Path):
    source = tmp_path / "source"; target = tmp_path / "target"
    source.mkdir(); target.mkdir()
    (source / "maths.py").write_text("def add(amount, name):\n    return amount + len(name)\n", encoding="utf-8")
    (target / "maths.py").write_text("def add(amount, name):\n    return amount + len(name)\n", encoding="utf-8")
    matches = [{"source": {"name": "add", "normalized": "add", "kind": "function", "arity": 2, "file": "maths.py"},
               "target": {"name": "add", "normalized": "add", "kind": "function", "arity": 2, "file": "maths.py"},
               "arity_compatible": True}]
    result = execute_behavioral_probes(source, target, matches)
    assert result["status"] == "passed"
    assert result["failed"] == 0
    assert result["passed"] == 3


def test_impure_functions_are_not_selected(tmp_path: Path):
    source = tmp_path / "source"; target = tmp_path / "target"
    source.mkdir(); target.mkdir()
    (source / "io.py").write_text("def read_file(path):\n    return open(path).read()\n", encoding="utf-8")
    (target / "io.py").write_text("def read_file(path):\n    return ''\n", encoding="utf-8")
    matches = [{"source": {"name": "read_file", "normalized": "readfile", "kind": "function", "arity": 1, "file": "io.py"},
               "target": {"name": "read_file", "normalized": "readfile", "kind": "function", "arity": 1, "file": "io.py"},
               "arity_compatible": True}]
    assert select_probe_candidates(source, target, matches) == []


def test_behavioral_probe_detects_source_target_output_mismatch(tmp_path: Path):
    source = tmp_path / "source"; target = tmp_path / "target"
    source.mkdir(); target.mkdir()
    (source / "maths.py").write_text("def add(amount, name):\n    return amount + len(name)\n", encoding="utf-8")
    (target / "maths.py").write_text("def add(amount, name):\n    return amount - len(name)\n", encoding="utf-8")
    matches = [{"source": {"name": "add", "normalized": "add", "kind": "function", "arity": 2, "file": "maths.py"},
               "target": {"name": "add", "normalized": "add", "kind": "function", "arity": 2, "file": "maths.py"},
               "arity_compatible": True}]
    result = execute_behavioral_probes(source, target, matches)
    assert result["status"] == "failed"
    assert result["failed"] > 0
