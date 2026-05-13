"""Integration tests for ``/auth/refresh`` and ``/auth/logout``."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.domain.entities.user import User

pytestmark = pytest.mark.integration


async def _login(api_client: AsyncClient, user: User, password: str) -> dict:
    response = await api_client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": password},
    )
    assert response.status_code == 200
    return response.json()


async def test_refresh_rotates_to_new_pair(api_client: AsyncClient, seeded_user: User) -> None:
    tokens = await _login(api_client, seeded_user, "long-enough-passphrase")
    response = await api_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": tokens["refresh_token"]},
    )
    assert response.status_code == 200, response.text
    new_tokens = response.json()
    assert new_tokens["access_token"] != tokens["access_token"]
    assert new_tokens["refresh_token"] != tokens["refresh_token"]


async def test_replay_revoked_refresh_token_returns_401(
    api_client: AsyncClient, seeded_user: User
) -> None:
    tokens = await _login(api_client, seeded_user, "long-enough-passphrase")
    # First rotation succeeds.
    first = await api_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": tokens["refresh_token"]},
    )
    assert first.status_code == 200
    # Replay of the original token must be rejected as REFRESH_TOKEN_REVOKED.
    replay = await api_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": tokens["refresh_token"]},
    )
    assert replay.status_code == 401
    assert replay.json()["code"] == "REFRESH_TOKEN_REVOKED"


async def test_malformed_refresh_token_returns_401(api_client: AsyncClient) -> None:
    response = await api_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": "garbage.not.a.jwt"},
    )
    assert response.status_code == 401


async def test_logout_revokes_refresh_token(api_client: AsyncClient, seeded_user: User) -> None:
    tokens = await _login(api_client, seeded_user, "long-enough-passphrase")
    logout = await api_client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": tokens["refresh_token"]},
    )
    assert logout.status_code == 204

    # Subsequent refresh with the same token must be rejected.
    response = await api_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": tokens["refresh_token"]},
    )
    assert response.status_code == 401
    assert response.json()["code"] == "REFRESH_TOKEN_REVOKED"


async def test_logout_is_idempotent(api_client: AsyncClient) -> None:
    # Unknown refresh token still returns 204.
    response = await api_client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": "garbage.not.a.jwt"},
    )
    assert response.status_code == 204
