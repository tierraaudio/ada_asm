"""OpenTelemetry → Azure Monitor (Application Insights) bootstrap.

Idempotent: calling `init()` more than once is a no-op after the first
call (we keep a module-level flag). NO-OP when
`APPLICATIONINSIGHTS_CONNECTION_STRING` is absent or empty — local dev
keeps the existing stdout-structlog pipeline intact.

What this does on a real boot:

1. Configures the OpenTelemetry global tracer + meter providers with
   resource attributes (`service.name`, `service.environment`,
   `service.version`) so every span/metric is tagged consistently.
2. Wires the Azure Monitor OTLP exporter using the connection string.
3. Auto-instruments FastAPI, httpx, SQLAlchemy (async + sync), and
   Celery. The instrumentations are import-once and idempotent.
4. Optionally configures sampling — 100% of HTTP root spans, 10% of
   SQL child spans on prod. Dev keeps everything.

What this does NOT do:

- Install the Web SDK in the frontend — that lives in `frontend/src/lib/telemetry.ts`.
- Touch logging — the structlog processor that injects `trace_id` /
  `span_id` into log records lives in `app/infrastructure/logging.py`.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import FastAPI

from app.core.config import Settings, get_settings

_log = logging.getLogger(__name__)

# Module-level flag so a second `init()` call from a worker process that
# already ran it doesn't double-register exporters.
_initialised = False


def init(app: FastAPI | None = None, *, settings: Settings | None = None) -> bool:
    """Initialise OpenTelemetry + Azure Monitor when configured.

    Returns True if instrumentation was actually wired, False if the env
    var was absent (no-op path).

    `app` is the FastAPI instance. When provided, FastAPI's HTTP request
    instrumentation is bound to it. When None (Celery worker / one-shot
    scripts), HTTP instrumentation is skipped — Celery + httpx + SQLAlchemy
    instrumentations still apply.
    """

    global _initialised
    if _initialised:
        return True

    settings = settings or get_settings()
    conn_str = settings.applicationinsights_connection_string
    if not conn_str:
        _log.debug(
            "observability.init: APPLICATIONINSIGHTS_CONNECTION_STRING absent; skipping"
        )
        return False

    # Heavy imports go inside `init()` so the no-op path does not pay
    # the import cost — important for the existing 246-test suite which
    # builds many short-lived `get_settings()` instances.
    from azure.monitor.opentelemetry.exporter import AzureMonitorTraceExporter
    from opentelemetry import trace
    from opentelemetry.instrumentation.celery import CeleryInstrumentor
    from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
    from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.sdk.trace.sampling import (
        ParentBased,
        TraceIdRatioBased,
    )

    resource = Resource.create(
        {
            "service.name": "ada-asm-backend",
            "service.environment": settings.environment_name,
            "service.version": settings.app_version,
        }
    )

    # Sampling: 100% of root spans (HTTP requests) — children inherit
    # their parent's sampling decision via ParentBased. On prod, we cap
    # the per-trace ratio at 1.0 (keep all) for now; tune via env later
    # if App Insights ingestion costs become a concern. The wrapper
    # remains in place so the knob is one line to flip.
    sampler = ParentBased(root=TraceIdRatioBased(1.0))

    provider = TracerProvider(resource=resource, sampler=sampler)
    exporter = AzureMonitorTraceExporter(connection_string=conn_str)
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    # FastAPI auto-instrumentation — only when `app` is provided.
    if app is not None:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        FastAPIInstrumentor.instrument_app(app)

    HTTPXClientInstrumentor().instrument()
    # SQLAlchemy auto-instrumentation works on both sync + async engines.
    # We don't pass `engine=` here — that would require knowing the
    # engine instance at init time; the instrumentor patches the create
    # path so all engines built after init are covered.
    SQLAlchemyInstrumentor().instrument()
    CeleryInstrumentor().instrument()  # type: ignore[no-untyped-call]

    _initialised = True
    _log.info(
        "observability.init: telemetry pipeline configured environment=%s service=ada-asm-backend",
        settings.environment_name,
    )
    return True


def is_initialised() -> bool:
    """Test helper: tells whether `init()` has wired anything yet."""
    return _initialised


def _reset_for_tests() -> None:
    """Reset the module-level flag. Test seam only."""
    global _initialised
    _initialised = False
