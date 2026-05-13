"""Integration tests for ``GET /api/v1/auth/me``."""

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
    return response.json()


async def test_me_returns_current_user(api_client: AsyncClient, seeded_user: User) -> None:
    tokens = await _login(api_client, seeded_user, "long-enough-passphrase")
    response = await api_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["email"] == seeded_user.email
    assert body["global_role"] == "user"
    assert "password_hash" not in body


async def test_me_without_authorization_returns_401(api_client: AsyncClient) -> None:
    response = await api_client.get("/api/v1/auth/me")
    assert response.status_code == 401
    assert response.json()["code"] == "UNAUTHENTICATED"


async def test_me_with_refresh_token_returns_401(
    api_client: AsyncClient, seeded_user: User
) -> None:
    tokens = await _login(api_client, seeded_user, "long-enough-passphrase")
    response = await api_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {tokens['refresh_token']}"},
    )
    assert response.status_code == 401
    assert response.json()["code"] == "ACCESS_TOKEN_WRONG_TYPE"


async def test_me_with_garbage_token_returns_401(api_client: AsyncClient) -> None:
    response = await api_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer not.a.jwt"},
    )
    assert response.status_code == 401
    assert response.json()["code"] in {
        "ACCESS_TOKEN_MALFORMED",
        "UNAUTHENTICATED",
    }
