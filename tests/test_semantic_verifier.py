from pathlib import Path

from agent_service.app.infrastructure.utils.semantic_verifier import extract_symbols, verify_migration_semantics


def test_extracts_python_public_contracts(tmp_path: Path):
    src = tmp_path / "src"; src.mkdir()
    (src / "service.py").write_text("class OrderService:\n    def create_order(self, user_id, amount):\n        return amount\n\ndef health():\n    return True\n", encoding="utf-8")
    symbols = extract_symbols(src)
    names = {x["name"] for x in symbols}
    assert {"OrderService", "health"} <= names
    order = next(x for x in symbols if x["name"] == "OrderService")
    assert order["methods"][0]["name"] == "create_order"
    assert order["methods"][0]["arity"] == 2


def test_verification_matches_cross_language_names(tmp_path: Path):
    source = tmp_path / "source"; target = tmp_path / "target"; source.mkdir(); target.mkdir()
    (source / "orders.py").write_text("def create_order(user_id, amount):\n    return amount\n\ndef cancel_order(order_id):\n    return True\n", encoding="utf-8")
    (target / "orders.ts").write_text("export function create_order(user_id, amount) { return amount; }\nexport function cancel_order(order_id) { return true; }\n", encoding="utf-8")
    result = verify_migration_semantics(source, target, persist=True)
    assert result["contract"]["matched"] == 2
    assert result["contract"]["missing"] == 0
    assert result["contract"]["arity_incompatible"] == 0
    assert (target / ".migration" / "semantic_verification.json").exists()


def test_verification_flags_missing_and_arity_mismatch(tmp_path: Path):
    source = tmp_path / "source"; target = tmp_path / "target"; source.mkdir(); target.mkdir()
    (source / "service.py").write_text("def calculate_total(a, b):\n    return a+b\n\ndef delete_item(item_id):\n    return True\n", encoding="utf-8")
    (target / "service.ts").write_text("export function calculate_total(a) { return a; }\n", encoding="utf-8")
    result = verify_migration_semantics(source, target, persist=False)
    assert result["contract"]["missing"] == 1
    assert result["contract"]["arity_incompatible"] == 1
    assert result["status"] == "partial"
