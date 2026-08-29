from app.infrastructure.utils import conversion_recipe_engine as engine


class _FakeTree:
    root_node = type("Root", (), {"has_error": lambda self: False})()


class _FakeParser:
    def __init__(self):
        self.seen = None

    def parse(self, source):
        assert isinstance(source, (bytes, bytearray)), type(source).__name__
        self.seen = source
        return _FakeTree()


def test_tree_sitter_validator_passes_utf8_bytes(monkeypatch):
    parser = _FakeParser()
    monkeypatch.setattr(engine, "_parser", lambda language: parser)
    result = engine.validate_target_fragment("class Calculator {}", "java")
    assert result.valid
    assert parser.seen == b"class Calculator {}\n"


def test_java_validator_does_not_expose_str_bytes_api_error(monkeypatch):
    parser = _FakeParser()
    monkeypatch.setattr(engine, "_parser", lambda language: parser)
    result = engine.validate_target_fragment("class Calculator {}", "java")
    assert all("bytestring or a callable" not in d for d in result.diagnostics)
