"""AuthService — the orchestration layer between the API and the domain.

The service is intentionally framework-agnostic. It accepts repositories via
protocols and an ``EmailSender`` instance via constructor injection; FastAPI
wires the concrete dependencies in ``app/api/v1/dependencies.py``.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

import structlog

from app.core.config import Settings
from app.core.exceptions import (
    InvalidCredentialsError,
    PasswordTooLongError,
    PasswordTooShortError,
    RefreshTokenExpiredError,
    RefreshTokenMalformedError,
    RefreshTokenRevokedError,
    ResetTokenAlreadyUsedError,
    ResetTokenExpiredError,
    ResetTokenInvalidError,
)
from app.domain.entities.password_reset_token import PasswordResetToken
from app.domain.entities.refresh_token import RefreshToken
from app.domain.entities.user import User
from app.domain.repositories.password_reset_token_repository import (
    PasswordResetTokenRepository,
)
from app.domain.repositories.refresh_token_repository import RefreshTokenRepository
from app.domain.repositories.user_repository import UserRepository
from app.infrastructure.email.sender import EmailSender
from app.infrastructure.jwt import (
    decode_access_token,
    decode_refresh_token,
    mint_access_token,
    mint_refresh_token,
)
from app.infrastructure.security import (
    argon2_hash,
    argon2_verify,
    hash_password,
    sha256_hex,
    verify_password,
)

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class IssuedTokens:
    access_token: str
    refresh_token: str
    expires_in: int  # seconds until the access token expires
    token_type: str = "bearer"


class AuthService:
    def __init__(
        self,
        *,
        settings: Settings,
        users: UserRepository,
        refresh_tokens: RefreshTokenRepository,
        password_reset_tokens: PasswordResetTokenRepository,
        email_sender: EmailSender,
    ) -> None:
        self._settings = settings
        self._users = users
        self._refresh_tokens = refresh_tokens
        self._reset_tokens = password_reset_tokens
        self._email = email_sender

    # ---------- Public surface ----------

    async def login(
        self,
        *,
        email: str,
        password: str,
        ip: str | None = None,
        user_agent: str | None = None,
    ) -> IssuedTokens:
        user = await self._users.get_by_email(email)
        if user is None:
            logger.info("auth.login.unknown_email", email=email)
            raise InvalidCredentialsError()
        if not user.is_active:
            logger.info("auth.login.inactive_user", user_id=str(user.id))
            raise InvalidCredentialsError()
        if not verify_password(password, user.password_hash):
            logger.info("auth.login.wrong_password", user_id=str(user.id))
            raise InvalidCredentialsError()

        return await self._issue_tokens(user, ip=ip, user_agent=user_agent)

    async def refresh(
        self,
        *,
        raw_refresh_token: str,
        ip: str | None = None,
        user_agent: str | None = None,
    ) -> IssuedTokens:
        claims = decode_refresh_token(raw_refresh_token)
        jti_hash = sha256_hex(claims.jti)
        existing = await self._refresh_tokens.get_by_jti_hash(jti_hash)
        if existing is None:
            raise RefreshTokenMalformedError()
        if existing.expires_at is not None and existing.expires_at < datetime.now(UTC):
            raise RefreshTokenExpiredError()
        if existing.is_revoked:
            logger.warning(
                "auth.refresh.replay",
                sub=str(claims.sub),
                jti=claims.jti,
            )
            raise RefreshTokenRevokedError()

        user = await self._users.get_by_id(claims.sub)
        if user is None or not user.is_active:
            raise RefreshTokenRevokedError()

        # Atomic rotation: revoke the presented token, then issue + persist the
        # new pair. Both operations share the request's session/transaction.
        await self._refresh_tokens.revoke(jti_hash)
        return await self._issue_tokens(user, ip=ip, user_agent=user_agent)

    async def logout(self, *, raw_refresh_token: str) -> None:
        """Idempotent — unknown / expired / already-revoked tokens are still 204.

        We never reveal whether the token was valid, to keep the endpoint
        from leaking session state.
        """
        try:
            claims = decode_refresh_token(raw_refresh_token)
        except Exception:
            return
        jti_hash = sha256_hex(claims.jti)
        await self._refresh_tokens.revoke(jti_hash)

    async def get_current_user(self, *, raw_access_token: str) -> User:
        claims = decode_access_token(raw_access_token)
        user = await self._users.get_by_id(claims.sub)
        if user is None or not user.is_active:
            raise InvalidCredentialsError()
        return user

    async def request_password_recovery(self, *, email: str) -> None:
        """Always succeeds from the caller's perspective; only inserts a
        token row + dispatches the email when ``email`` belongs to an active
        user."""
        user = await self._users.get_by_email(email)
        if user is None or not user.is_active:
            logger.info("auth.password_recovery.unknown_or_inactive", email=email)
            return

        raw_token = secrets.token_urlsafe(48)
        token = PasswordResetToken(
            user_id=user.id,
            token_hash=argon2_hash(raw_token),
            expires_at=datetime.now(UTC)
            + timedelta(seconds=self._settings.password_reset_token_ttl_seconds),
        )
        await self._reset_tokens.save(token)

        reset_url = (
            f"{self._settings.frontend_base_url.rstrip('/')}/reset-password?token={raw_token}"
        )
        await self._email.send(
            to=user.email,
            subject="Restablecer tu contraseña en ADA ASM",
            body_text=(
                "Hola,\n\n"
                "Recibimos una solicitud para restablecer tu contraseña en ADA ASM.\n"
                "Si la has solicitado tú, abre el siguiente enlace para elegir una "
                "contraseña nueva:\n\n"
                f"{reset_url}\n\n"
                "El enlace caduca en una hora. Si no has solicitado el cambio, puedes "
                "ignorar este mensaje."
            ),
        )

    async def reset_password(self, *, raw_token: str, new_password: str) -> None:
        self._enforce_password_policy(new_password)

        token = await self._find_reset_token(raw_token)
        if token is None:
            raise ResetTokenInvalidError()
        if token.is_used:
            raise ResetTokenAlreadyUsedError()
        if token.expires_at is not None and token.expires_at < datetime.now(UTC):
            raise ResetTokenExpiredError()

        await self._users.update_password(token.user_id, hash_password(new_password))
        await self._reset_tokens.mark_used(token)
        await self._refresh_tokens.revoke_all_for_user(token.user_id)

    async def revoke_all_refresh_tokens(self, user_id: UUID) -> int:
        return await self._refresh_tokens.revoke_all_for_user(user_id)

    # ---------- Private helpers ----------

    async def _issue_tokens(
        self,
        user: User,
        *,
        ip: str | None = None,
        user_agent: str | None = None,
    ) -> IssuedTokens:
        access_token, _access_jti, access_exp = mint_access_token(user)
        refresh_token, refresh_jti, refresh_exp = mint_refresh_token(user)

        await self._refresh_tokens.save(
            RefreshToken(
                user_id=user.id,
                jti_hash=sha256_hex(refresh_jti),
                expires_at=refresh_exp,
                created_from_ip=ip,
                user_agent=user_agent,
            )
        )

        return IssuedTokens(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=int((access_exp - datetime.now(UTC)).total_seconds()),
        )

    async def _find_reset_token(self, raw_token: str) -> PasswordResetToken | None:
        # Linear scan over unused, unexpired tokens — usually one or two rows.
        # Each candidate is verified with Argon2; we accept the cost because
        # password resets are rare events on the request budget.
        candidates = await self._reset_tokens.list_active()
        for candidate in candidates:
            if argon2_verify(raw_token, candidate.token_hash):
                return candidate
        return None

    def _enforce_password_policy(self, password: str) -> None:
        if len(password) < self._settings.password_min_length:
            raise PasswordTooShortError(
                f"Password must be at least {self._settings.password_min_length} characters"
            )
        if len(password) > self._settings.password_max_length:
            raise PasswordTooLongError(
                f"Password must be at most {self._settings.password_max_length} characters"
            )
