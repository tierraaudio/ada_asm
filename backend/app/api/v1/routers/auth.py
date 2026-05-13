"""Authentication endpoints — login, refresh, logout, me, password recovery & reset."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response, status
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.api.v1.dependencies import get_auth_service, require_user
from app.api.v1.schemas.auth import (
    LoginRequest,
    LogoutRequest,
    MeResponse,
    PasswordRecoveryRequest,
    PasswordRecoveryResponse,
    PasswordResetRequest,
    RefreshRequest,
    TokenResponse,
)
from app.application.services.auth_service import AuthService
from app.core.config import get_settings
from app.domain.entities.user import User

limiter = Limiter(key_func=get_remote_address)

router = APIRouter(prefix="/auth", tags=["auth"])


def _login_limit() -> str:
    """Resolved on every request — lets tests vary the limit via env."""
    return f"{get_settings().login_rate_limit_per_minute}/minute"


@router.post("/login", response_model=TokenResponse, status_code=200)
@limiter.limit(_login_limit)
async def login(
    request: Request,
    payload: LoginRequest,
    auth: Annotated[AuthService, Depends(get_auth_service)],
) -> TokenResponse:
    tokens = await auth.login(
        email=payload.email,
        password=payload.password,
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    return TokenResponse(**tokens.__dict__)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    request: Request,
    payload: RefreshRequest,
    auth: Annotated[AuthService, Depends(get_auth_service)],
) -> TokenResponse:
    tokens = await auth.refresh(
        raw_refresh_token=payload.refresh_token,
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    return TokenResponse(**tokens.__dict__)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    payload: LogoutRequest,
    auth: Annotated[AuthService, Depends(get_auth_service)],
) -> Response:
    await auth.logout(raw_refresh_token=payload.refresh_token)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/password-recovery",
    response_model=PasswordRecoveryResponse,
    status_code=202,
)
@limiter.limit(_login_limit)
async def password_recovery(
    request: Request,
    payload: PasswordRecoveryRequest,
    auth: Annotated[AuthService, Depends(get_auth_service)],
) -> PasswordRecoveryResponse:
    await auth.request_password_recovery(email=payload.email)
    return PasswordRecoveryResponse()


@router.post("/password-reset", status_code=status.HTTP_204_NO_CONTENT)
async def password_reset(
    payload: PasswordResetRequest,
    auth: Annotated[AuthService, Depends(get_auth_service)],
) -> Response:
    await auth.reset_password(
        raw_token=payload.token,
        new_password=payload.new_password,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me", response_model=MeResponse)
async def me(user: Annotated[User, Depends(require_user)]) -> MeResponse:
    return MeResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        global_role=user.global_role,
        is_active=user.is_active,
        created_at=user.created_at,
    )
