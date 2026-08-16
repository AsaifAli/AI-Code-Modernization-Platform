import os
import logging
from dotenv import load_dotenv

from agno.models.ollama import Ollama
from agno.models.google import Gemini
from agno.models.openai import OpenAIChat
from app.infrastructure.utils.llm_gateway_context import get_llm_gateway_token
from agno.models.huggingface import HuggingFace
from agno.knowledge.embedder.openai import OpenAIEmbedder
from agno.knowledge.embedder.google import GeminiEmbedder
from agno.knowledge.embedder.ollama import OllamaEmbedder
from agno.knowledge.embedder.fastembed import FastEmbedEmbedder
import hashlib
import math

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
OPENAI_MODEL_ID = os.getenv("LLM_MODEL") or os.getenv("OPENAI_MODEL_ID", "gpt-4o")
OPENAI_BASE_URL = os.getenv("LLM_BASE_URL") or os.getenv("OPENAI_BASE_URL")
LLM_GATEWAY_URL = os.getenv("LLM_GATEWAY_URL", "https://portfolio-llm-gateway.onrender.com/v1").strip()
LLM_GATEWAY_TIMEOUT = float(os.getenv("LLM_GATEWAY_TIMEOUT", "180"))
EMBED_MODEL_TYPE = os.getenv("EMBED_MODEL_TYPE", "fastembed").strip().lower()
EMBED_DIMENSIONS = int(os.getenv("EMBED_DIMENSIONS", "384"))
EMBEDDING_BASE_URL = os.getenv("EMBEDDING_BASE_URL")
VLLM_BASE_URL = os.getenv("VLLM_BASE_URL")
VLLM_CHAT_MODEL_ID = os.getenv("VLLM_CHAT_MODEL_ID")
VLLM_EMBED_MODEL_ID = os.getenv("VLLM_EMBED_MODEL_ID")
VLLM_EMBEDDING_BASE_URL = os.getenv("VLLM_EMBEDDING_BASE_URL")
VLLM_API_KEY = os.getenv("VLLM_API_KEY") or "local"
# --------------------------------------------------
# Embedding: Local vLLM
# --------------------------------------------------
class VLLMEmbedder:
    """Custom embedder for vLLM OpenAI-compatible embedding endpoint"""
    def __init__(self, base_url: str, model: str):
        logger.info("🚀 Initializing VLLMEmbedder")
        self.client = OpenAI(
            base_url=base_url,
            api_key=VLLM_API_KEY
        )
        self.model = model
        # Detect embedding dimension
        test = self.client.embeddings.create(
            model=self.model,
            input="test"
        )
        self.dimensions = len(test.data[0].embedding)
        logger.info(f"✅ Embedding dimension detected: {self.dimensions}")
    def embed_documents(self, texts):
        logger.info(f"📥 Embedding documents | count={len(texts)}")
        response = self.client.embeddings.create(
            model=self.model,
            input=texts
        )
        return [d.embedding for d in response.data]
    def embed_query(self, text):
        logger.debug(f"🔍 Embedding query")
        response = self.client.embeddings.create(
            model=self.model,
            input=text
        )
        return response.data[0].embedding
    # AGNO compatibility
    def get_embedding(self, text):
        return self.embed_query(text)
    def get_embedding_and_usage(self, text):
        embedding = self.embed_query(text)
        usage = {
            "prompt_tokens": 0,
            "total_tokens": 0
        }
        return embedding, usage
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
        if token:
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
                max_retries=max(int(self.max_retries or 0), 2),
                default_headers=self.default_headers,
                default_query=self.default_query,
            )
        return super().get_client()

    def get_async_client(self):
        token, gateway_url = self._gateway_config()
        if token:
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
                max_retries=max(int(self.max_retries or 0), 2),
                default_headers=self.default_headers,
                default_query=self.default_query,
            )
        return super().get_async_client()


class LowMemoryHashEmbedder:
    """Dependency-free fallback embedder for small Render instances.

    Produces deterministic, normalized vectors using hashed token/character
    features. It avoids loading an ONNX embedding model into the service.
    For this demo-oriented deployment, LanceDB can still perform vector/
    lexical retrieval without the memory spike caused by FastEmbed startup.
    """

    def __init__(self, dimensions: int = 384):
        self.id = "portfolio-hash-embedder"
        self.dimensions = dimensions

    @staticmethod
    def _tokens(text: str):
        text = str(text or "").lower()
        tokens = []
        cur = []
        for ch in text:
            if ch.isalnum() or ch == "_":
                cur.append(ch)
            elif cur:
                tokens.append("".join(cur))
                cur = []
        if cur:
            tokens.append("".join(cur))
        return tokens

    def get_embedding(self, text):
        vec = [0.0] * self.dimensions
        tokens = self._tokens(text)
        if not tokens:
            return vec
        for token in tokens:
            for feature in (token, token[:3], token[-3:]):
                digest = hashlib.blake2b(feature.encode("utf-8"), digest_size=8).digest()
                idx = int.from_bytes(digest, "little") % self.dimensions
                sign = 1.0 if (digest[0] & 1) else -1.0
                vec[idx] += sign
        norm = math.sqrt(sum(x * x for x in vec)) or 1.0
        return [x / norm for x in vec]

    def get_embedding_and_usage(self, text):
        return self.get_embedding(text), {"prompt_tokens": 0, "total_tokens": 0}

    def embed_documents(self, texts):
        return [self.get_embedding(t) for t in texts]


def create_embedder():
    if EMBED_MODEL_TYPE in {"hash", "low_memory", "low-memory"}:
        logger.warning("Using low-memory deterministic embeddings for constrained deployment")
        return LowMemoryHashEmbedder(dimensions=EMBED_DIMENSIONS)
    return FastEmbedEmbedder(id=os.getenv("FASTEMBED_MODEL", "BAAI/bge-small-en-v1.5"), dimensions=EMBED_DIMENSIONS)

# --------------------------------------------------
# Model Factory
# --------------------------------------------------
def create_model_and_embedder():
    """Factory to initialize model + embedder based on MODEL_TYPE"""
    if MODEL_TYPE == "OpenAI":
        model = GatewayAwareOpenAIChat(
            id=OPENAI_MODEL_ID,
            api_key=os.getenv("OPENAI_API_KEY"),
            base_url=OPENAI_BASE_URL,
            temperature=0.1
        )
        embedder = create_embedder()
        logger.info("Using OpenAI-compatible model with constrained local embeddings")
    elif MODEL_TYPE == "VLLM":
        if not VLLM_CHAT_MODEL_ID or not VLLM_BASE_URL:
            raise ValueError("VLLM config missing")
        model = VLLMCompatibleOpenAIChat(
            id=VLLM_CHAT_MODEL_ID,
            base_url=VLLM_BASE_URL,
            api_key=VLLM_API_KEY,
            temperature=0.1
        )
        embedder = create_embedder()
        logger.info(f"✅ Using vLLM model: {VLLM_CHAT_MODEL_ID}")
    elif MODEL_TYPE == "Gemini":
        model = Gemini(
            id=os.getenv("GEMINI_MODEL_ID"),
            api_key=os.getenv("GOOGLE_API_KEY"),
            temperature=0.1
        )
        embedder = create_embedder()
        logger.info("✅ Using Gemini model")
    elif MODEL_TYPE == "Ollama":
        model = Ollama(
            id=os.getenv("OLLAMA_MODEL_ID"),
            host=os.getenv("OLLAMA_HOST"),
            supports_native_structured_outputs=True,
            supports_json_schema_outputs=True,
            options={"temperature": 0.1, "num_ctx": 256000}
        )
        embedder = FastEmbedEmbedder()
        logger.info("✅ Using Ollama model")
    elif MODEL_TYPE == "HuggingFace":
        model = HuggingFace(
            id=os.getenv("HUGGINGFACE_MODEL_ID"),
            api_key=os.getenv("HUGGINGFACE_API_KEY"),
            supports_native_structured_outputs=True,
            supports_json_schema_outputs=True,
        )
        embedder = create_embedder()
        logger.info("✅ Using configured local embeddings")
    else:
        raise ValueError(f"Unsupported MODEL_TYPE: {MODEL_TYPE}")
    return model, embedder
# --------------------------------------------------
# Initialize
# --------------------------------------------------
model, model_embedder = create_model_and_embedder()