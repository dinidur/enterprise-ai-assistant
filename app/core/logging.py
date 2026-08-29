"""Structured JSON logging.

The assessment requires structured logging. Human-readable console output is
used locally; machine-parsable JSON everywhere else, so logs can be shipped to
an aggregator and correlated with LangSmith traces via ``request_id``.
"""

import logging
import sys
from typing import Any

import structlog

from app.core.config import settings


def configure_logging() -> None:
    """Configure ``structlog`` once at application startup."""
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
    )

    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    renderer: Any = (
        structlog.dev.ConsoleRenderer()
        if settings.app_env == "local"
        else structlog.processors.JSONRenderer()
    )

    structlog.configure(
        processors=[*shared_processors, renderer],
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Return a bound logger for the given module name."""
    return structlog.get_logger(name)


def bind_request_context(**kwargs: Any) -> None:
    """Bind values (request_id, user_id, session_id, role) to every later log
    line in the current async context."""
    structlog.contextvars.bind_contextvars(**kwargs)


def clear_request_context() -> None:
    """Clear per-request bound context. Call at the end of each request."""
    structlog.contextvars.clear_contextvars()
