from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODEL_PROVIDER = ROOT / "agent_service/app/infrastructure/agents_backend/model_provider.py"
ROUTER = ROOT / "agent_service/app/presentation/routes/agent_router.py"
RENDER = ROOT / "render.yaml"


def test_render_is_gateway_only():
    text = RENDER.read_text(encoding="utf-8")
    assert 'LLM_GATEWAY_URL' in text
    assert 'LLM_GATEWAY_REQUIRED' in text
    assert 'OPENAI_BASE_URL' not in text
    assert 'OPENAI_API_KEY' not in text
    assert 'LLM_MODEL' not in text


def test_model_provider_has_no_direct_openai_fallback():
    text = MODEL_PROVIDER.read_text(encoding="utf-8")
    assert 'return super().get_client()' not in text
    assert 'return super().get_async_client()' not in text
    assert 'LLM gateway session token is required' in text
    assert 'api_key="gateway-session"' in text


def test_ai_routes_require_and_propagate_gateway_token():
    text = ROUTER.read_text(encoding="utf-8")
    assert text.count('alias="X-LLM-Gateway-Token"') >= 5
    assert '_require_llm_gateway_token' in text
    assert 'background_tasks.add_task(execute_agent_team, task_id, request, str(user.id), gateway_token)' in text
    assert 'gateway_token,' in text
