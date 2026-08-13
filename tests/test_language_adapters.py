from pathlib import Path

from app.infrastructure.utils.language_adapters import adapters, detect_by_extension, get_adapter
from app.infrastructure.utils.post_migration_engine import checks_for_stack, generate_ci_workflow


def test_adapter_registry_covers_supported_ecosystems():
    keys = {a.key for a in adapters()}
    assert {"python", "node", "java", "go", "php", "dotnet"} <= keys
    assert all(a.check_builder is not None for a in adapters())


def test_extension_detection_uses_registry(tmp_path: Path):
    (tmp_path / "main.go").write_text("package main\n", encoding="utf-8")
    assert detect_by_extension(tmp_path) == "go"


def test_checks_are_resolved_through_adapter(tmp_path: Path):
    (tmp_path / "go.mod").write_text("module example.com/demo\n\ngo 1.23\n", encoding="utf-8")
    names = {c[0] for c in checks_for_stack(tmp_path, "go")}
    assert {"go-test", "go-build", "go-vet"} <= names


def test_ci_generation_is_adapter_owned(tmp_path: Path):
    path = generate_ci_workflow(tmp_path, "go")
    assert path is not None
    text = path.read_text(encoding="utf-8")
    assert "actions/setup-go@v5" in text
    assert "go test ./..." in text
    assert "npm" not in text


def test_unknown_stack_has_no_fake_validation_adapter(tmp_path: Path):
    adapter = get_adapter("cobol")
    assert adapter is None
    assert checks_for_stack(tmp_path, "cobol") == []
