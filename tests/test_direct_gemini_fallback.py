import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "agent_service"
sys.path.insert(0, str(ROOT))


def test_model_config_does_not_use_legacy_llm_model(monkeypatch):
    monkeypatch.delenv("LLM_MODEL", raising=False)
    monkeypatch.setenv("OPENAI_MODEL_ID", "gemini-2.5-flash")
    monkeypatch.setenv("LLM_DIRECT_PROVIDER", "google")
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
    from app.infrastructure.agents_backend import model_provider
    assert model_provider.OPENAI_MODEL_ID == "gemini-2.5-flash"
    assert model_provider.DIRECT_PROVIDER == "google"


def test_deterministic_target_hint_preserves_explicit_java_target(monkeypatch):
    from app.application.agents.utility_agent import _deterministic_target_hints
    hints = _deterministic_target_hints("Convert python to java using Spring Boot")
    assert hints["target_language"] == "java"
    assert hints["target_framework"] == "spring boot"
