import json
from pathlib import Path

from app.infrastructure.utils.dependency_artifact_utils import extract_dependency_packages
from app.infrastructure.utils.migration_packager import package_migrated_code


def test_package_json_dependency_extraction_ignores_json_syntax():
    content = json.dumps({"dependencies": {"express": "latest"}, "devDependencies": {"pytest": "latest"}})
    assert extract_dependency_packages("package.json", content) == ["express", "pytest"]


def test_package_json_dependency_extraction_handles_empty_manifest():
    assert extract_dependency_packages("package.json", '{"dependencies": {}}') == []


def test_packager_blocks_dependency_only_plan(tmp_path: Path):
    migrated = tmp_path / "Migrated Code"
    migrated.mkdir()
    (migrated / "package.json").write_text('{"dependencies":{"express":"latest"}}')
    plan = {
        "src": {
            "plans": [
                {"symbol_id": "dependency_file", "migration_status": "dependency_file"}
            ]
        }
    }
    (tmp_path / "migration_plan.json").write_text(json.dumps(plan))
    result = package_migrated_code(tmp_path, "smoke")
    assert "No source-symbol migration plans" in result
    assert not (tmp_path / "smoke_processed.zip").exists()


def test_packager_allows_real_symbol_plan(tmp_path: Path):
    migrated = tmp_path / "Migrated Code"
    migrated.mkdir()
    (migrated / "index.js").write_text("export function add(a,b){return a+b}\n")
    plan = {
        "src": {
            "plans": [
                {"symbol_id": "src_add", "migration_status": "completed"}
            ]
        }
    }
    (tmp_path / "migration_plan.json").write_text(json.dumps(plan))
    result = package_migrated_code(tmp_path, "smoke")
    assert "Packaged converted project" in result
    assert (tmp_path / "smoke_processed.zip").exists()
