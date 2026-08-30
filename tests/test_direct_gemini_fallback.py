import importlib
import inspect


def test_model_config_does_not_use_legacy_llm_model(monkeypatch):
    monkeypatch.delenv("LLM_MODEL", raising=False)
    monkeypatch.setenv("OPENAI_MODEL_ID", "gemini-2.5-flash")
    module = importlib.import_module("app.infrastructure.agents_backend.model_provider")
    assert module.OPENAI_MODEL_ID == "gemini-2.5-flash"


def test_gateway_model_requires_request_scoped_jwt(monkeypatch):
    module = importlib.import_module("app.infrastructure.agents_backend.model_provider")
    monkeypatch.delenv("LLM_GATEWAY_URL", raising=False)
    module.get_llm_gateway_token = lambda: ""
    model = module.GatewayAwareOpenAIChat(id="gateway-managed")
    try:
        model.get_client()
    except RuntimeError as exc:
        assert "LLM gateway session token is required" in str(exc)
    else:
        raise AssertionError("Gateway client must fail closed without a JWT")


def test_gateway_model_uses_request_scoped_token(monkeypatch):
    module = importlib.import_module("app.infrastructure.agents_backend.model_provider")
    monkeypatch.setenv("LLM_GATEWAY_URL", "https://gateway.example.invalid/v1")
    monkeypatch.setattr(module, "get_llm_gateway_token", lambda: "test-jwt")
    model = module.GatewayAwareOpenAIChat(id="gateway-managed")
    client = model.get_client()
    assert client.api_key == "test-jwt"
    assert str(client.base_url).rstrip("/") == "https://gateway.example.invalid/v1"


def test_gateway_model_contains_no_direct_provider_fallback():
    module = importlib.import_module("app.infrastructure.agents_backend.model_provider")
    source = inspect.getsource(module.GatewayAwareOpenAIChat)
    assert "GOOGLE_API_KEY" not in source
    assert "OpenRouter" not in source
    assert "super().get_client()" not in source
    assert "super().get_async_client()" not in source
