import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODEL_PROVIDER = ROOT / "agent_service/app/infrastructure/agents_backend/model_provider.py"


def test_model_config_does_not_use_legacy_llm_model(monkeypatch):
    monkeypatch.delenv("LLM_MODEL", raising=False)
    monkeypatch.setenv("OPENAI_MODEL_ID", "gemini-2.5-flash")
    monkeypatch.setenv("LLM_DIRECT_PROVIDER", "google")

    # This setting is retained only as a compatibility/read-only value.
    # Runtime routing remains Gateway-only and never uses a direct provider.
    source = MODEL_PROVIDER.read_text(encoding="utf-8")
    assert 'OPENAI_MODEL_ID = os.getenv("OPENAI_MODEL_ID", "gateway-managed")' in source
    assert 'DIRECT_PROVIDER = os.getenv("LLM_DIRECT_PROVIDER", "")' in source
    assert 'return super().get_client()' not in source
    assert 'return super().get_async_client()' not in source
