"""FastAPI application factory.

The factory pattern keeps the ASGI app testable: tests build a fresh app
with their own settings without touching the import-time state of a module
level ``app`` global.
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.v1 import api_v1_router
from app.core.config import Settings, get_settings
from app.infrastructure.logging import configure_logging, request_id_ctx

REQUEST_ID_HEADER = "X-Request-ID"


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Bind an ``X-Request-ID`` to every request/response.

    Reads an inbound header if present, otherwise generates a UUID4. Sets the
    structlog context var so every log line emitted during the request
    includes the same identifier.
    """

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        request_id = request.headers.get(REQUEST_ID_HEADER) or str(uuid.uuid4())
        token = request_id_ctx.set(request_id)
        try:
            response = await call_next(request)
        finally:
            request_id_ctx.reset(token)
        response.headers[REQUEST_ID_HEADER] = request_id
        return response


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(env=settings.env, log_level=settings.log_level)

    app = FastAPI(
        title="ADA ASM API",
        version=settings.app_version,
        docs_url="/docs" if settings.env != "production" else None,
        redoc_url=None,
        openapi_url="/openapi.json",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RequestIdMiddleware)

    app.include_router(api_v1_router)
    return app


app = create_app()
