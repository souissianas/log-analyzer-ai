"""
core/logging_config.py
Structured JSON logging for Loki ingestion + correlation ID propagation.
"""
from __future__ import annotations

import contextvars
import logging
import sys
import uuid

try:
    from pythonjsonlogger import json as jsonlogger  # type: ignore  # ≥ 3.x
except ImportError:
    from pythonjsonlogger import jsonlogger  # type: ignore  # 2.x fallback

# Context variable — propagated across async tasks
correlation_id_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "correlation_id", default=""
)


class CorrelationIdFilter(logging.Filter):
    """Injects the current correlation_id into every log record."""

    def filter(self, record: logging.LogRecord) -> bool:  # noqa: A003
        record.correlation_id = correlation_id_var.get("")
        return True


def setup_logging(level: str = "INFO") -> None:
    """
    Configure root logger with JSON formatter.
    Call once at application startup (before any other imports log).
    """
    handler = logging.StreamHandler(sys.stdout)
    formatter = jsonlogger.JsonFormatter(
        fmt="%(asctime)s %(name)s %(levelname)s %(message)s %(correlation_id)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
        rename_fields={"asctime": "timestamp", "levelname": "level", "name": "logger"},
    )
    handler.setFormatter(formatter)
    handler.addFilter(CorrelationIdFilter())

    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
    root.handlers = [handler]

    # Reduce noise from noisy libs
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)


def generate_correlation_id() -> str:
    """Generate a new short UUID v4 correlation ID."""
    return str(uuid.uuid4())[:8]


def set_correlation_id(cid: str) -> None:
    correlation_id_var.set(cid)


def get_correlation_id() -> str:
    return correlation_id_var.get("")
