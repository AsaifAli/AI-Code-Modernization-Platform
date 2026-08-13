from pathlib import Path

from portfolio_quality.quality_gate import run


def test_quality_gate_accepts_clean_fixture(tmp_path: Path):
    (tmp_path / "sample.py").write_text("def hello():\n    return 'world'\n", encoding="utf-8")
    (tmp_path / ".env.example").write_text("API_KEY=change-me\n", encoding="utf-8")
    result = run(tmp_path)
    assert result["passed"]


def test_quality_gate_rejects_env_file(tmp_path: Path):
    (tmp_path / ".env").write_text("API_KEY=secret\n", encoding="utf-8")
    result = run(tmp_path)
    assert not result["passed"]
    assert any("forbidden artifact" in error for error in result["errors"])


def test_quality_gate_rejects_invalid_python(tmp_path: Path):
    (tmp_path / "broken.py").write_text("def broken(:\n", encoding="utf-8")
    result = run(tmp_path)
    assert not result["passed"]
    assert any("syntax error" in error for error in result["errors"])
