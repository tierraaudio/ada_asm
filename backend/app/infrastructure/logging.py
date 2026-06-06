"""Structured logging configuration.

Outputs JSON in non-development environments and a console renderer when
``ENV=development``. Binds a ``request_id`` to a context variable so every
log line emitted while handling a request includes it automatically.
"""

from __future__ import annotations

import logging
import sys
from collections.abc import MutableMapping
from contextvars import ContextVar
from typing import Any

import structlog

request_id_ctx: ContextVar[str | None] = ContextVar("request_id", default=None)


def _add_request_id(
    _: Any,
    __: str,
    event_dict: MutableMapping[str, Any],
) -> MutableMapping[str, Any]:
    request_id = request_id_ctx.get()
    if request_id is not None:
        event_dict["request_id"] = request_id
    return event_dict


def _add_trace_context(
    _: Any,
    __: str,
    event_dict: MutableMapping[str, Any],
) -> MutableMapping[str, Any]:
    """Inject the active OpenTelemetry span's `trace_id` + `span_id` into
    every log record so App Insights correlates logs with traces.

    No-op when OpenTelemetry is not configured (the import resolves but
    the global tracer provider is a NoOp) or when no span is active.
    Lazy import so the structlog pipeline keeps working even if OTel is
    not installed at all (e.g. in a stripped-down build).
    """

    try:
        from opentelemetry import trace
    except ImportError:
        return event_dict

    span = trace.get_current_span()
    ctx = span.get_span_context()
    if ctx.is_valid:
        # W3C-format hex strings so App Insights' correlation works
        # without extra parsing on the ingestion side.
        event_dict["trace_id"] = format(ctx.trace_id, "032x")
        event_dict["span_id"] = format(ctx.span_id, "016x")
    return event_dict


def configure_logging(env: str, log_level: str) -> None:
    """Configure structlog and the stdlib logger.

    Idempotent — safe to call on every app boot.
    """
    level = getattr(logging, log_level.upper(), logging.INFO)

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=level,
    )

    processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        _add_request_id,
        _add_trace_context,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if env == "development":
        processors.append(structlog.dev.ConsoleRenderer())
    else:
        processors.append(structlog.processors.JSONRenderer())

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
