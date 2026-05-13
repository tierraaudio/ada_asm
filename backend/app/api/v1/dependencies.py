"""FastAPI dependency providers for the v1 API."""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Annotated

from fastapi import Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.services.auth_service import AuthService
from app.core.config import Settings, get_settings
from app.core.exceptions import ForbiddenError, UnauthenticatedError
from app.domain.entities.user import User
from app.domain.repositories.password_reset_token_repository import (
    PasswordResetTokenRepository,
)
from app.domain.repositories.refresh_token_repository import RefreshTokenRepository
from app.domain.repositories.user_repository import UserRepository
from app.infrastructure.db.session import get_db_session as _get_db_session
from app.infrastructure.email import EmailSender
from app.infrastructure.email import get_email_sender as _get_email_sender
from app.infrastructure.repositories.password_reset_token_repository import (
    SqlAlchemyPasswordResetTokenRepository,
)
from app.infrastructure.repositories.refresh_token_repository import (
    SqlAlchemyRefreshTokenRepository,
)
from app.infrastructure.repositories.user_repository import SqlAlchemyUserRepository


async def get_db_session() -> AsyncIterator[AsyncSession]:
    async for session in _get_db_session():
        yield session


def get_user_repository(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> UserRepository:
    return SqlAlchemyUserRepository(session)


def get_refresh_token_repository(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> RefreshTokenRepository:
    return SqlAlchemyRefreshTokenRepository(session)


def get_password_reset_token_repository(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> PasswordResetTokenRepository:
    return SqlAlchemyPasswordResetTokenRepository(session)


def get_email_sender() -> EmailSender:
    return _get_email_sender()


def get_auth_service(
    settings: Annotated[Settings, Depends(get_settings)],
    users: Annotated[UserRepository, Depends(get_user_repository)],
    refresh_tokens: Annotated[RefreshTokenRepository, Depends(get_refresh_token_repository)],
    reset_tokens: Annotated[
        PasswordResetTokenRepository, Depends(get_password_reset_token_repository)
    ],
    email_sender: Annotated[EmailSender, Depends(get_email_sender)],
) -> AuthService:
    return AuthService(
        settings=settings,
        users=users,
        refresh_tokens=refresh_tokens,
        password_reset_tokens=reset_tokens,
        email_sender=email_sender,
    )


async def require_user(
    request: Request,
    auth: Annotated[AuthService, Depends(get_auth_service)],
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
) -> User:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise UnauthenticatedError("Missing or malformed Authorization header")
    token = authorization.split(" ", 1)[1].strip()
    user = await auth.get_current_user(raw_access_token=token)
    request.state.current_user = user
    return user


def require_role(*allowed_roles: str) -> Callable[..., Awaitable[User]]:
    """Factory: returns a dependency that ensures the current user has one of
    the given global roles. Per-project roles will reuse the same shape via a
    separate factory introduced in a later capability."""

    async def _checker(user: Annotated[User, Depends(require_user)]) -> User:
        if user.global_role not in allowed_roles:
            raise ForbiddenError(f"Required role: {', '.join(allowed_roles)}")
        return user

    return _checker
