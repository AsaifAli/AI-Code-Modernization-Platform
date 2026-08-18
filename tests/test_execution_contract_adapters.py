from pathlib import Path

from app.infrastructure.utils.language_adapters import (
    ExecutionContract,
    adapter_for_file,
    get_adapter,
)


def test_python_execution_contract_is_source_adapter_owned(tmp_path: Path):
    source = tmp_path / "Calculator.py"
    source.write_text(
        "def calculator():\n"
        "    print('ok')\n"
        "\n"
        "calculator()\n",
        encoding="utf-8",
    )

    adapter = adapter_for_file(source)
    assert adapter is not None
    contract = adapter.detect_execution_contract(source, "calculator")
    assert contract == ExecutionContract(True, "calculator", "module-level invocation")


def test_java_entrypoint_is_target_adapter_owned():
    adapter = get_adapter("java")
    assert adapter is not None
    contract = ExecutionContract(True, "calculator", "module-level invocation")
    code = (
        "public class Calculator {\n"
        "    public void calculate() {\n"
        "        System.out.println(1 + 1);\n"
        "    }\n"
        "}\n"
    )
    result = adapter.ensure_entrypoint(code, contract, "calculator")
    assert "static void main(String[] args)" in result
    assert "new Calculator().calculate();" in result


def test_non_executable_contract_is_not_rewritten():
    adapter = get_adapter("java")
    assert adapter is not None
    contract = ExecutionContract(False, "calculator", "reusable module or no detected invocation")
    code = "public class Calculator { public void calculate() {} }\n"
    assert adapter.ensure_entrypoint(code, contract, "calculator") == code


def test_shared_conversion_layer_has_no_java_entrypoint_helper():
    conversion_tools = Path(__file__).parents[1] / "agent_service/app/application/agents/conversion/conversion_tools.py"
    source = conversion_tools.read_text(encoding="utf-8")
    assert "_ensure_java_entrypoint" not in source
    assert "adapter_for_file" in source
    assert "ensure_entrypoint" in source
