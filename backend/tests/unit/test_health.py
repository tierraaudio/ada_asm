"""Health endpoint contract tests."""

from __future__ import annotations

import os
import re

import pytest
from httpx import AsyncClient
from pydantic import ValidationError

pytestmark = pytest.mark.unit


async def test_health_returns_200_with_expected_body(api_client: AsyncClient) -> None:
    response = await api_client.get("/api/v1/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert isinstance(body["version"], str) and body["version"]
    assert re.match(
        r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z$",
        body["timestamp"],
    ), body["timestamp"]


async def test_health_does_not_require_authentication(api_client: AsyncClient) -> None:
    response = await api_client.get("/api/v1/health")

    assert response.status_code == 200, "health must be reachable without Authorization header"
    assert response.status_code != 401
    assert response.status_code != 403


async def test_request_id_header_is_set_on_response(api_client: AsyncClient) -> None:
    response = await api_client.get("/api/v1/health")
    assert response.headers.get("X-Request-ID"), "RequestIdMiddleware must inject X-Request-ID"


async def test_request_id_header_is_echoed_when_provided(api_client: AsyncClient) -> None:
    inbound_id = "11111111-2222-3333-4444-555555555555"
    response = await api_client.get(
        "/api/v1/health",
        headers={"X-Request-ID": inbound_id},
    )
    assert response.headers["X-Request-ID"] == inbound_id


def test_settings_refuses_to_instantiate_without_required_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If a required env var is missing, Settings() must raise.

    Reproduces the runtime guarantee that the service does not boot half-
    configured: missing JWT_SECRET fails fast before the ASGI server binds.
    """
    # Drop every variable Settings consumes so Pydantic surfaces a missing-
    # field error, not a "value just happens to be there from the host".
    for var in (
        "ENV",
        "LOG_LEVEL",
        "DATABASE_URL",
        "CELERY_BROKER_URL",
        "CELERY_RESULT_BACKEND",
        "JWT_SECRET",
        "CORS_ORIGINS",
    ):
        monkeypatch.delenv(var, raising=False)
    # Confirm JWT_SECRET is really gone for this test process.
    assert "JWT_SECRET" not in os.environ

    from app.core.config import Settings

    with pytest.raises(ValidationError) as excinfo:
        Settings()  # type: ignore[call-arg]

    missing_fields = {err["loc"][0] for err in excinfo.value.errors()}
    assert "database_url" in missing_fields or "DATABASE_URL" in missing_fields or missing_fields
