from pathlib import Path

from agent_service.app.infrastructure.utils.post_migration_engine import (
    detect_target_stack,
    generate_ci_workflow,
    validate_migrated_project,
)


def test_detect_python_stack(tmp_path: Path):
    (tmp_path / "pyproject.toml").write_text("[project]\nname='demo'\n", encoding="utf-8")
    info = detect_target_stack(tmp_path)
    assert info["stack"] == "python"


def test_generate_ci_is_non_destructive(tmp_path: Path):
    (tmp_path / "requirements.txt").write_text("pytest\n", encoding="utf-8")
    ci = generate_ci_workflow(tmp_path, "python")
    assert ci is not None
    assert ci.exists()
    original = ci.read_text(encoding="utf-8")
    ci2 = generate_ci_workflow(tmp_path, "python")
    assert ci2 == ci
    assert ci.read_text(encoding="utf-8") == original


def test_python_project_quality_gate(tmp_path: Path):
    (tmp_path / "pyproject.toml").write_text("[project]\nname='demo'\n", encoding="utf-8")
    (tmp_path / "calculator.py").write_text(
        "def add(a: int, b: int) -> int:\n    return a + b\n",
        encoding="utf-8",
    )
    (tmp_path / "test_calculator.py").write_text(
        "from calculator import add\n\n\ndef test_add():\n    assert add(2, 3) == 5\n",
        encoding="utf-8",
    )
    report = validate_migrated_project(
        tmp_path,
        migration_name="engine-test",
        max_repair_attempts=0,
        persist=True,
    )
    assert report["target_stack"]["stack"] == "python"
    assert report["release_ready"] is True
    assert (tmp_path / ".migration" / "quality_report.json").exists()
