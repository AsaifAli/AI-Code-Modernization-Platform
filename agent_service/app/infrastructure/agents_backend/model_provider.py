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
# from agno.models.vllm import VLLM
from openai import OpenAI
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
LLM_GATEWAY_URL = os.getenv("LLM_GATEWAY_URL", "").strip()
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
    """OpenAI-compatible model that can use a request-scoped gateway token.

    The normal deployment path keeps the existing environment-based credential.
    Interactive portfolio demos can attach X-LLM-Gateway-Token to the API request;
    the token is stored in a ContextVar and used for a short-lived gateway call.
    """
    def _effective_model(self):
        token = get_llm_gateway_token()
        if not token or not LLM_GATEWAY_URL:
            return self
        return OpenAIChat(
            id=self.id,
            api_key=token,
            base_url=LLM_GATEWAY_URL,
            temperature=getattr(self, "temperature", 0.1),
        )

    def invoke(self, messages, **kwargs):
        model = self._effective_model()
        if model is self:
            return super().invoke(messages, **kwargs)
        return model.invoke(messages, **kwargs)

    async def ainvoke(self, messages, **kwargs):
        model = self._effective_model()
        if model is self:
            return await super().ainvoke(messages, **kwargs)
        return await model.ainvoke(messages, **kwargs)
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
        embedder = FastEmbedEmbedder()
        logger.info("Using OpenAI-compatible model with FastEmbed local embeddings")
    elif MODEL_TYPE == "VLLM":
        if not VLLM_CHAT_MODEL_ID or not VLLM_BASE_URL:
            raise ValueError("VLLM config missing")
        model = VLLMCompatibleOpenAIChat(
            id=VLLM_CHAT_MODEL_ID,
            base_url=VLLM_BASE_URL,
            api_key=VLLM_API_KEY,
            temperature=0.1
        )
        embedder = FastEmbedEmbedder()
        logger.info(f"✅ Using vLLM model: {VLLM_CHAT_MODEL_ID}")
    elif MODEL_TYPE == "Gemini":
        model = Gemini(
            id=os.getenv("GEMINI_MODEL_ID"),
            api_key=os.getenv("GOOGLE_API_KEY"),
            temperature=0.1
        )
        embedder = FastEmbedEmbedder()
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
        embedder = FastEmbedEmbedder()
        logger.info("✅ Using FastEmbed local embeddings")
    else:
        raise ValueError(f"Unsupported MODEL_TYPE: {MODEL_TYPE}")
    return model, embedder
# --------------------------------------------------
# Initialize
# --------------------------------------------------
model, model_embedder = create_model_and_embedder()