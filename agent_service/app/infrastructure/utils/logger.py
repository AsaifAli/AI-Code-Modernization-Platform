"""Application logging helpers with request/task correlation."""
from __future__ import annotations

import logging
import os

from app.infrastructure.utils.request_context import request_id_ctx


class RequestContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_ctx.get()
        return True


def configure_logging() -> None:
    level = os.getenv("LOG_LEVEL", "INFO").upper()
    root = logging.getLogger()
    root.setLevel(level)
    if not root.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s %(levelname)s request_id=%(request_id)s %(name)s - %(message)s"
            )
        )
        handler.addFilter(RequestContextFilter())
        root.addHandler(handler)
    else:
        for handler in root.handlers:
            handler.addFilter(RequestContextFilter())
