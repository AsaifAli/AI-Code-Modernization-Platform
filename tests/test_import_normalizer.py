from pathlib import Path

from app.infrastructure.utils.import_normalizer import normalize_imports_in_tree


def test_python_imports_are_hoisted(tmp_path: Path):
    p = tmp_path / "example.py"
    p.write_text(
        '"""module"""\n\nclass A:\n    pass\n\nimport os\nfrom pathlib import Path\n\ndef f():\n    return os.getcwd()\n',
        encoding="utf-8",
    )
    result = normalize_imports_in_tree(tmp_path)
    assert result["files_changed"] == 1
    text = p.read_text(encoding="utf-8")
    assert text.index("import os") < text.index("class A")
    assert text.index("from pathlib import Path") < text.index("class A")


def test_javascript_imports_are_hoisted(tmp_path: Path):
    p = tmp_path / "example.js"
    p.write_text(
        "export function a() { return 1; }\nimport fs from 'fs';\n",
        encoding="utf-8",
    )
    normalize_imports_in_tree(tmp_path)
    text = p.read_text(encoding="utf-8")
    assert text.index("import fs") < text.index("export function a")
