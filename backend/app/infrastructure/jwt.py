"""JWT minting and decoding for access and refresh tokens.

We use HS256 with the application's ``JWT_SECRET``. Both token kinds share
the same secret and algorithm; they are distinguished by the ``type`` claim
(``access`` vs ``refresh``) and by ``exp``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Literal
from uuid import UUID, uuid4

from jose import JWTError, jwt

from app.core.config import get_settings
from app.core.exceptions import (
    AccessTokenExpiredError,
    AccessTokenMalformedError,
    AccessTokenWrongTypeError,
    RefreshTokenExpiredError,
    RefreshTokenMalformedError,
)
from app.domain.entities.user import User

ALGORITHM = "HS256"

TokenType = Literal["access", "refresh"]


@dataclass(frozen=True)
class TokenClaims:
    sub: UUID
    type: TokenType
    jti: str
    exp: datetime
    iat: datetime
    email: str | None = None
    roles: tuple[str, ...] = ()
    project_scopes: tuple[str, ...] = ()


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _mint(
    *,
    user: User,
    token_type: TokenType,
    ttl_seconds: int,
    extra_claims: dict[str, Any] | None = None,
) -> tuple[str, str, datetime]:
    settings = get_settings()
    now = _utc_now()
    exp = now + timedelta(seconds=ttl_seconds)
    jti = uuid4().hex
    payload: dict[str, Any] = {
        "sub": str(user.id),
        "type": token_type,
        "jti": jti,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
    }
    if extra_claims:
        payload.update(extra_claims)
    token = jwt.encode(payload, settings.jwt_secret, algorithm=ALGORITHM)
    return token, jti, exp


def mint_access_token(user: User) -> tuple[str, str, datetime]:
    """Returns (encoded_token, jti, expires_at)."""
    settings = get_settings()
    extra = {
        "email": user.email,
        "roles": [user.global_role],
        "project_scopes": ["*"],
    }
    return _mint(
        user=user,
        token_type="access",
        ttl_seconds=settings.jwt_access_token_ttl_seconds,
        extra_claims=extra,
    )


def mint_refresh_token(user: User) -> tuple[str, str, datetime]:
    """Returns (encoded_token, jti, expires_at)."""
    settings = get_settings()
    return _mint(
        user=user,
        token_type="refresh",
        ttl_seconds=settings.jwt_refresh_token_ttl_seconds,
    )


def _decode(raw: str) -> dict[str, Any]:
    settings = get_settings()
    decoded: dict[str, Any] = jwt.decode(raw, settings.jwt_secret, algorithms=[ALGORITHM])
    return decoded


def decode_access_token(raw: str) -> TokenClaims:
    try:
        payload = _decode(raw)
    except JWTError as exc:
        msg = str(exc).lower()
        if "expired" in msg or "signature has expired" in msg:
            raise AccessTokenExpiredError() from exc
        raise AccessTokenMalformedError() from exc

    if payload.get("type") != "access":
        raise AccessTokenWrongTypeError()

    return _to_claims(payload)


def decode_refresh_token(raw: str) -> TokenClaims:
    try:
        payload = _decode(raw)
    except JWTError as exc:
        msg = str(exc).lower()
        if "expired" in msg:
            raise RefreshTokenExpiredError() from exc
        raise RefreshTokenMalformedError() from exc

    if payload.get("type") != "refresh":
        raise RefreshTokenMalformedError()

    return _to_claims(payload)


def _to_claims(payload: dict[str, Any]) -> TokenClaims:
    return TokenClaims(
        sub=UUID(payload["sub"]),
        type=payload["type"],
        jti=payload["jti"],
        exp=datetime.fromtimestamp(payload["exp"], UTC),
        iat=datetime.fromtimestamp(payload["iat"], UTC),
        email=payload.get("email"),
        roles=tuple(payload.get("roles", ())),
        project_scopes=tuple(payload.get("project_scopes", ())),
    )
