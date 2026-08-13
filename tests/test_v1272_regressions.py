from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PM = ROOT / "agent_service/app/infrastructure/utils/Agent_helpers/post_migration_helper.py"
SC = ROOT / "agent_service/app/infrastructure/utils/Agent_helpers/scanner_helper.py"
CV = ROOT / "agent_service/app/application/agents/conversion/conversion_tools.py"


def test_post_migration_rehydrates_serialized_check_results():
    text = PM.read_text(encoding="utf-8")
    assert "CheckResult" in text
    assert "repair_results: list[CheckResult]" in text
    assert "CheckResult(" in text


def test_scanner_imports_migration_directory():
    text = SC.read_text(encoding="utf-8")
    import_line = next(line for line in text.splitlines() if line.startswith("from app.infrastructure.utils.file_utils import"))
    assert "get_migration_directory" in import_line


def test_conversion_has_graph_fallback_for_source_symbol_completion():
    text = CV.read_text(encoding="utf-8")
    assert "knowledge_graph.json" in text
    assert "source_symbol_id" in text
    assert "rehydrated from knowledge_graph.json" in text
