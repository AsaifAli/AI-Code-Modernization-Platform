from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[1]
MODEL_PROVIDER = ROOT / "agent_service/app/infrastructure/agents_backend/model_provider.py"


def test_model_config_does_not_use_legacy_llm_model():
    source = MODEL_PROVIDER.read_text(encoding="utf-8")
    tree = ast.parse(source)

    assignments = {}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    assignments[target.id] = node.value

    # OPENAI_MODEL_ID must be independently configurable and must not
    # inherit from the removed legacy LLM_MODEL variable.
    openai_node = assignments.get("OPENAI_MODEL_ID")
    assert openai_node is not None

    rendered = ast.unparse(openai_node)
    assert "LLM_MODEL" not in rendered
    assert "OPENAI_MODEL_ID" in rendered
    assert "gateway-managed" in rendered


def test_gateway_aware_model_requires_request_scoped_gateway_token():
    source = MODEL_PROVIDER.read_text(encoding="utf-8")
    assert "get_llm_gateway_token()" in source
    assert "LLM gateway session token is required" in source
    assert 'api_key=token' in source
    assert 'base_url=gateway_url' in source


def test_no_direct_google_fallback_is_used_by_gateway_aware_model():
    source = MODEL_PROVIDER.read_text(encoding="utf-8")
    start = source.index("class GatewayAwareOpenAIChat")
    end = source.index("# --------------------------------------------------\n# Model Factory", start)
    gateway_section = source[start:end]

    assert "GOOGLE_API_KEY" not in gateway_section
    assert "Gemini(" not in gateway_section
    assert "OpenRouter" not in gateway_section
