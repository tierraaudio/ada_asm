"""Unit tests for the security primitives and JWT roundtrip."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.core.exceptions import (
    AccessTokenExpiredError,
    AccessTokenMalformedError,
    AccessTokenWrongTypeError,
    RefreshTokenExpiredError,
    RefreshTokenMalformedError,
)
from app.domain.entities.user import User
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

pytestmark = pytest.mark.unit


def _make_user() -> User:
    return User(
        id=uuid4(),
        email="x@example.com",
        password_hash="",
        full_name="X",
        global_role="user",
        is_active=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


def test_hash_password_uses_argon2id() -> None:
    digest = hash_password("a-long-enough-passphrase")
    assert digest.startswith("$argon2id$")
    assert verify_password("a-long-enough-passphrase", digest) is True
    assert verify_password("wrong", digest) is False


def test_argon2_token_roundtrip() -> None:
    digest = argon2_hash("some-random-token")
    assert digest.startswith("$argon2id$")
    assert argon2_verify("some-random-token", digest) is True
    assert argon2_verify("other", digest) is False


def test_sha256_hex_is_deterministic() -> None:
    assert sha256_hex("abc") == sha256_hex("abc")
    assert sha256_hex("abc") != sha256_hex("abd")


def test_mint_and_decode_access_token() -> None:
    user = _make_user()
    token, jti, exp = mint_access_token(user)
    claims = decode_access_token(token)
    assert claims.sub == user.id
    assert claims.type == "access"
    assert claims.jti == jti
    assert "user" in claims.roles
    assert "*" in claims.project_scopes
    assert exp > datetime.now(UTC)


def test_mint_and_decode_refresh_token() -> None:
    user = _make_user()
    token, jti, exp = mint_refresh_token(user)
    claims = decode_refresh_token(token)
    assert claims.sub == user.id
    assert claims.type == "refresh"
    assert claims.jti == jti
    assert exp > datetime.now(UTC)


def test_access_token_with_wrong_type_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    user = _make_user()
    refresh, _, _ = mint_refresh_token(user)
    with pytest.raises(AccessTokenWrongTypeError):
        decode_access_token(refresh)


def test_refresh_token_with_wrong_type_raises() -> None:
    user = _make_user()
    access, _, _ = mint_access_token(user)
    with pytest.raises(RefreshTokenMalformedError):
        decode_refresh_token(access)


def test_decode_garbage_raises_malformed() -> None:
    with pytest.raises(AccessTokenMalformedError):
        decode_access_token("not.a.real.jwt")


def test_expired_access_token_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    from datetime import datetime as real_datetime

    user = _make_user()
    monkeypatch.setenv("JWT_ACCESS_TOKEN_TTL_SECONDS", "-1")
    from app.core.config import get_settings

    get_settings.cache_clear() if hasattr(get_settings, "cache_clear") else None

    # Mint a token that is already past its expiry by going negative on TTL.
    token, _, exp = mint_access_token(user)
    assert exp < real_datetime.now(UTC) + timedelta(seconds=1)
    with pytest.raises(AccessTokenExpiredError):
        decode_access_token(token)


def test_expired_refresh_token_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    user = _make_user()
    monkeypatch.setenv("JWT_REFRESH_TOKEN_TTL_SECONDS", "-1")
    token, _, _ = mint_refresh_token(user)
    with pytest.raises(RefreshTokenExpiredError):
        decode_refresh_token(token)
