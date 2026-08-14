from contextvars import ContextVar

_llm_gateway_token: ContextVar[str] = ContextVar("llm_gateway_token", default="")


def set_llm_gateway_token(token: str):
    return _llm_gateway_token.set((token or "").strip())


def get_llm_gateway_token() -> str:
    return _llm_gateway_token.get()
