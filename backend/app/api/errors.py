"""HTTP error mapping — turns domain exceptions into RFC 7807 responses."""

from __future__ import annotations

import structlog
from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.exceptions import DomainError, RateLimitExceededError

logger = structlog.get_logger(__name__)


def _problem(
    *,
    request: Request,
    status: int,
    code: str,
    title: str,
    detail: str | None = None,
    extra: dict[str, object] | None = None,
) -> JSONResponse:
    body: dict[str, object] = {
        "type": f"https://ada-asm/errors/{code.lower().replace('_', '-')}",
        "title": title,
        "status": status,
        "code": code,
        "instance": str(request.url.path),
    }
    if detail:
        body["detail"] = detail
    if extra:
        body.update(extra)
    return JSONResponse(status_code=status, content=jsonable_encoder(body))


async def domain_error_handler(request: Request, exc: DomainError) -> JSONResponse:
    return _problem(
        request=request,
        status=exc.http_status,
        code=exc.code,
        title=_title_for(exc.code),
        detail=str(exc) if str(exc) != exc.__class__.__name__ else None,
        extra=exc.extra or None,
    )


async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    return _problem(
        request=request,
        status=422,
        code="VALIDATION_ERROR",
        title="Request validation failed",
        detail="One or more fields failed validation; see the 'errors' field.",
        extra={"errors": jsonable_encoder(exc.errors())},
    )


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    return _problem(
        request=request,
        status=exc.status_code,
        code=_default_code_for_status(exc.status_code),
        title=str(exc.detail)
        if exc.detail
        else _title_for(_default_code_for_status(exc.status_code)),
    )


async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    err = RateLimitExceededError("Too many requests")
    response = _problem(
        request=request,
        status=err.http_status,
        code=err.code,
        title="Rate limit exceeded",
        detail=str(exc.detail) if exc.detail else None,
    )
    response.headers["Retry-After"] = "60"
    return response


def install(app: FastAPI) -> None:
    app.add_exception_handler(DomainError, domain_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, validation_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)  # type: ignore[arg-type]


# ---------- Helpers ----------


def _title_for(code: str) -> str:
    return code.replace("_", " ").title()


def _default_code_for_status(status: int) -> str:
    return {
        400: "BAD_REQUEST",
        401: "UNAUTHENTICATED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        409: "CONFLICT",
        422: "VALIDATION_ERROR",
        429: "RATE_LIMIT_EXCEEDED",
    }.get(status, "ERROR")
