from contextvars import ContextVar

# Thread-safe storage for current user
current_user: ContextVar = ContextVar("current_user", default=None)
