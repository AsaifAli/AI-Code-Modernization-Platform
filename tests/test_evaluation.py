from pathlib import Path

from evaluation.evaluate_migration import collect_stats, evaluate


def test_collect_stats_counts_python_symbols(tmp_path: Path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "app.py").write_text(
        "class Service:\n    def run(self):\n        return 1\n\ndef helper():\n    return 2\n",
        encoding="utf-8",
    )
    stats = collect_stats(source)
    assert stats.files == 1
    assert stats.symbols == 3
    assert stats.python_syntax_valid == 1


def test_evaluate_returns_deterministic_metrics(tmp_path: Path):
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    target.mkdir()
    (source / "app.py").write_text("def run():\n    return 1\n", encoding="utf-8")
    (target / "app.py").write_text("def run():\n    return 2\n", encoding="utf-8")
    result = evaluate(source, target)
    assert result["metrics"]["relative_file_coverage_percent"] == 100.0
    assert result["metrics"]["python_syntax_validity_percent"] == 100.0


def test_evaluate_can_run_behavioral_benchmark(tmp_path: Path):
    source = tmp_path / "source"
    target = tmp_path / "target"
    (source).mkdir()
    (target / "tests").mkdir(parents=True)
    (source / "app.py").write_text("def run():\n    return 1\n", encoding="utf-8")
    (target / "app.py").write_text("def run():\n    return 1\n", encoding="utf-8")
    (target / "tests" / "test_app.py").write_text(
        "import unittest\n\nclass TestApp(unittest.TestCase):\n    def test_smoke(self):\n        self.assertEqual(1 + 1, 2)\n",
        encoding="utf-8",
    )
    result = evaluate(
        source,
        target,
        test_command="python -m unittest discover -s tests",
        test_cwd=target,
    )
    assert result["behavioral_validation"]["passed"] is True
