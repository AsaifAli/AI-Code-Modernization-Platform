"""Request correlation context used for API logs and error responses."""
from contextvars import ContextVar

request_id_ctx: ContextVar[str] = ContextVar("request_id", default="-")
