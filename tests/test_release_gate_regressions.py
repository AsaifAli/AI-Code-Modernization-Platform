
import json
from pathlib import Path

from agent_service.app.infrastructure.utils.post_migration_engine import (
    check_node_repository_integrity,
    validate_migrated_project,
)
from agent_service.app.infrastructure.utils.migration_packager import package_migrated_code


def test_node_repository_integrity_rejects_mixed_exports_and_missing_import(tmp_path: Path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "utils.js").write_text(
        "const x = require('./missing');\nexport function ok() {}\nmodule.exports = { ok };\nmodule.exports = { x };\n",
        encoding="utf-8",
    )
    assert check_node_repository_integrity(tmp_path) is False


def test_node_project_with_tests_requires_test_script(tmp_path: Path):
    (tmp_path / "package.json").write_text(
        json.dumps({"name": "demo", "dependencies": {}}), encoding="utf-8"
    )
    (tmp_path / "app.js").write_text("module.exports = {};\n", encoding="utf-8")
    (tmp_path / "app.test.js").write_text("test('x',()=>{});\n", encoding="utf-8")
    report = validate_migrated_project(tmp_path, migration_name="gate", max_repair_attempts=0)
    assert report["release_ready"] is False
    assert any(c["name"] == "node-test-command" and c["status"] == "failed"
               for c in report["checks"])


def test_packager_excludes_macos_metadata(tmp_path: Path):
    migration = tmp_path / "migration"
    code = migration / "Migrated Code"
    code.mkdir(parents=True)
    (migration / "migration_plan.json").write_text(
        json.dumps({"module": {"plans": [{"symbol_id": "fn-1"}]}}), encoding="utf-8"
    )
    (code / "app.js").write_text("module.exports = {};\n", encoding="utf-8")
    (code / ".DS_Store").write_text("junk", encoding="utf-8")
    (code / "._app.js").write_text("junk", encoding="utf-8")
    (code / "__MACOSX").mkdir()
    (code / "__MACOSX" / "._app.js").write_text("junk", encoding="utf-8")
    result = package_migrated_code(migration, "demo")
    assert "Packaged converted project" in result
    import zipfile
    with zipfile.ZipFile(migration / "demo_processed.zip") as z:
        names = z.namelist()
        assert names == ["app.js"]


def test_knowledge_base_thresholds_default_is_defined():
    from pathlib import Path
    source_path = Path("agent_service/app/application/agents/knowledge_base/knowledge_base_tools.py")
    source = source_path.read_text(encoding="utf-8")
    assert "thresholds = {}" in source
    assert 'f"hierarchy_thresholds": thresholds' in source


def test_main_migration_workflow_uses_direct_post_migration_executor():
    from pathlib import Path
    source = Path("agent_service/app/infrastructure/workflows/migration_workflow.py").read_text(encoding="utf-8")
    assert "from app.application.agents.post_migration.post_migration_agent import _run_post_migration" in source
    assert "executor=_run_post_migration" in source
    assert "workflow=post_migration_workflow" not in source


def test_post_migration_executor_normalizes_status_to_step_output():
    from pathlib import Path
    source = Path("agent_service/app/application/agents/post_migration/post_migration_agent.py").read_text(encoding="utf-8")
    assert 'blocked = status in {"blocked", "not_ready"}' in source
    assert "success=not blocked" in source
    assert "stop=blocked" in source
    assert "content=result if isinstance(result, str)" in source
