import os
import logging
from dotenv import load_dotenv

from agno.models.ollama import Ollama
from agno.models.google import Gemini
from agno.models.openai import OpenAIChat
from app.infrastructure.utils.llm_gateway_context import get_llm_gateway_token
from agno.models.huggingface import HuggingFace

# from agno.models.vllm import VLLM
from openai import AsyncOpenAI, OpenAI
# --------------------------------------------------
# Setup
# --------------------------------------------------
load_dotenv()
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)
# --------------------------------------------------
# Environment Variables
# --------------------------------------------------
MODEL_TYPE = os.getenv("MODEL_TYPE", "OpenAI")
OPENAI_MODEL_ID = os.getenv("LLM_MODEL") or os.getenv("OPENAI_MODEL_ID", "gateway-managed")
LLM_GATEWAY_URL = os.getenv("LLM_GATEWAY_URL", "https://portfolio-llm-gateway.onrender.com/v1").strip()
LLM_GATEWAY_TIMEOUT = float(os.getenv("LLM_GATEWAY_TIMEOUT", "180"))
# Demo/portfolio gateways commonly rate-limit bursts. Avoid immediate SDK retries
# that amplify a 429; make the value configurable for production.
LLM_GATEWAY_MAX_RETRIES = max(0, int(os.getenv("LLM_GATEWAY_MAX_RETRIES", "0")))
VLLM_BASE_URL = os.getenv("VLLM_BASE_URL")
VLLM_CHAT_MODEL_ID = os.getenv("VLLM_CHAT_MODEL_ID")
VLLM_API_KEY = os.getenv("VLLM_API_KEY") or "local"
# --------------------------------------------------
# Message Normalization (vLLM compatibility)
# --------------------------------------------------
def normalize_messages(messages):
    """Ensure only 'user' and 'assistant' roles are sent to vLLM"""
    allowed_roles = {"user", "assistant"}
    normalized = []
    for msg in messages:
        # AGNO Message object
        if hasattr(msg, "role"):
            if getattr(msg, "role", None) not in allowed_roles:
                setattr(msg, "role", "user")
            normalized.append(msg)
        # Dict fallback
        elif isinstance(msg, dict):
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role not in allowed_roles:
                role = "user"
            normalized.append({
                "role": role,
                "content": content
            })
    return normalized
# --------------------------------------------------
# Safe OpenAI Chat Wrapper (vLLM compatible)
# --------------------------------------------------
class VLLMCompatibleOpenAIChat(OpenAIChat):
    """Wrapper to make AGNO + vLLM compatible."""
    def invoke(self, messages, **kwargs):
        logger.debug("🔧 Normalizing messages for vLLM")
        messages = normalize_messages(messages)
        return super().invoke(messages, **kwargs)


class GatewayAwareOpenAIChat(OpenAIChat):
    """OpenAI-compatible Agno model with request-scoped portfolio gateway support.

    The deployed LegacyLens API receives a short-lived gateway JWT in
    ``X-LLM-Gateway-Token``. The router carries it into the background task,
    where ``WorkflowOrchestrator`` binds it to a ContextVar.

    Agno's OpenAIChat performs all sync/async/streaming calls through
    ``get_client()`` / ``get_async_client()``. We therefore override those
    two methods instead of overriding ``invoke()``. This keeps the normal
    Agno request lifecycle intact while ensuring the per-request gateway
    credential is used for every completion call without mutating global
    environment variables or a shared cached client.
    """

    def _gateway_config(self):
        token = get_llm_gateway_token().strip()
        gateway_url = LLM_GATEWAY_URL.strip()
        if gateway_url.endswith("/"):
            gateway_url = gateway_url[:-1]
        return token, gateway_url

    def get_client(self):
        token, gateway_url = self._gateway_config()
        if not token:
            raise RuntimeError(
                "LLM gateway session token is required. Pass X-LLM-Gateway-Token from the portfolio session."
            )
        if not gateway_url:
            raise RuntimeError("LLM gateway token present but LLM_GATEWAY_URL is not configured")
        logger.info(
            "Using request-scoped Portfolio LLM Gateway for model=%s base_url=%s",
            self.id,
            gateway_url,
        )
        return OpenAI(
            api_key=token,
            base_url=gateway_url,
            timeout=max(float(self.timeout or 0), LLM_GATEWAY_TIMEOUT),
            max_retries=LLM_GATEWAY_MAX_RETRIES if self.max_retries in (None, 0) else int(self.max_retries),
            default_headers=self.default_headers,
            default_query=self.default_query,
        )

    def get_async_client(self):
        token, gateway_url = self._gateway_config()
        if not token:
            raise RuntimeError(
                "LLM gateway session token is required. Pass X-LLM-Gateway-Token from the portfolio session."
            )
        if not gateway_url:
            raise RuntimeError("LLM gateway token present but LLM_GATEWAY_URL is not configured")
        logger.info(
            "Using request-scoped Portfolio LLM Gateway (async) for model=%s base_url=%s",
            self.id,
            gateway_url,
        )
        return AsyncOpenAI(
            api_key=token,
            base_url=gateway_url,
            timeout=max(float(self.timeout or 0), LLM_GATEWAY_TIMEOUT),
            max_retries=LLM_GATEWAY_MAX_RETRIES if self.max_retries in (None, 0) else int(self.max_retries),
            default_headers=self.default_headers,
            default_query=self.default_query,
        )



# --------------------------------------------------
# Model Factory
# --------------------------------------------------
def create_model():
    """Initialize only the chat model. KB embeddings live in Qdrant Cloud."""
    if MODEL_TYPE == "OpenAI":
        model = GatewayAwareOpenAIChat(
            id=OPENAI_MODEL_ID,
            api_key="gateway-session",
            base_url=LLM_GATEWAY_URL,
            temperature=0.1,
        )
        logger.info("Using OpenAI-compatible model with request-scoped gateway support")
    elif MODEL_TYPE == "VLLM":
        if not VLLM_CHAT_MODEL_ID or not VLLM_BASE_URL:
            raise ValueError("VLLM config missing")
        model = VLLMCompatibleOpenAIChat(
            id=VLLM_CHAT_MODEL_ID,
            base_url=VLLM_BASE_URL,
            api_key=VLLM_API_KEY,
            temperature=0.1,
        )
        logger.info("Using vLLM model: %s", VLLM_CHAT_MODEL_ID)
    elif MODEL_TYPE == "Gemini":
        model = Gemini(
            id=os.getenv("GEMINI_MODEL_ID"),
            api_key=os.getenv("GOOGLE_API_KEY"),
            temperature=0.1,
        )
        logger.info("Using Gemini model")
    elif MODEL_TYPE == "Ollama":
        model = Ollama(
            id=os.getenv("OLLAMA_MODEL_ID"),
            host=os.getenv("OLLAMA_HOST"),
            supports_native_structured_outputs=True,
            supports_json_schema_outputs=True,
            options={"temperature": 0.1, "num_ctx": 256000},
        )
        logger.info("Using Ollama model")
    elif MODEL_TYPE == "HuggingFace":
        model = HuggingFace(
            id=os.getenv("HUGGINGFACE_MODEL_ID"),
            api_key=os.getenv("HUGGINGFACE_API_KEY"),
            supports_native_structured_outputs=True,
            supports_json_schema_outputs=True,
        )
        logger.info("Using configured HuggingFace chat model")
    else:
        raise ValueError(f"Unsupported MODEL_TYPE: {MODEL_TYPE}")
    return model


model = create_model()
# Backward-compatibility alias only. No local embedding model is instantiated.
model_embedder = None
