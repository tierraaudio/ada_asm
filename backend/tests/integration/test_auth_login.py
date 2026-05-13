"""Integration tests for ``POST /api/v1/auth/login``."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.domain.entities.user import User
from app.infrastructure.jwt import decode_access_token, decode_refresh_token

pytestmark = pytest.mark.integration


async def test_valid_credentials_issue_both_tokens(
    api_client: AsyncClient, seeded_user: User
) -> None:
    response = await api_client.post(
        "/api/v1/auth/login",
        json={"email": seeded_user.email, "password": "long-enough-passphrase"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] > 0
    access_claims = decode_access_token(body["access_token"])
    assert access_claims.sub == seeded_user.id
    assert access_claims.type == "access"
    assert seeded_user.email == access_claims.email
    refresh_claims = decode_refresh_token(body["refresh_token"])
    assert refresh_claims.type == "refresh"
    assert refresh_claims.sub == seeded_user.id


async def test_unknown_email_returns_uniform_401(api_client: AsyncClient) -> None:
    response = await api_client.post(
        "/api/v1/auth/login",
        json={"email": "ghost@nowhere.example", "password": "doesnotmatter12345"},
    )
    assert response.status_code == 401
    body = response.json()
    assert body["code"] == "INVALID_CREDENTIALS"


async def test_wrong_password_returns_uniform_401(
    api_client: AsyncClient, seeded_user: User
) -> None:
    response = await api_client.post(
        "/api/v1/auth/login",
        json={"email": seeded_user.email, "password": "definitely-wrong-pass"},
    )
    assert response.status_code == 401
    assert response.json()["code"] == "INVALID_CREDENTIALS"


async def test_inactive_user_returns_uniform_401(
    api_client: AsyncClient, seeded_inactive: User
) -> None:
    response = await api_client.post(
        "/api/v1/auth/login",
        json={"email": seeded_inactive.email, "password": "ghost-long-passphrase"},
    )
    assert response.status_code == 401
    assert response.json()["code"] == "INVALID_CREDENTIALS"


async def test_invalid_email_format_returns_422(api_client: AsyncClient) -> None:
    response = await api_client.post(
        "/api/v1/auth/login",
        json={"email": "not-an-email", "password": "anything-valid-12345"},
    )
    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"


async def test_response_bodies_are_byte_identical_for_unknown_and_wrong_password(
    api_client: AsyncClient, seeded_user: User
) -> None:
    a = await api_client.post(
        "/api/v1/auth/login",
        json={"email": "ghost@nowhere.example", "password": "doesnotmatter12345"},
    )
    b = await api_client.post(
        "/api/v1/auth/login",
        json={"email": seeded_user.email, "password": "wrong-password-xx"},
    )
    # The `instance` field includes the URL path; both bodies post to the same
    # endpoint, so the full payload should match.
    assert a.json() == b.json()
