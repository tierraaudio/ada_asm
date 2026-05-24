"""Integration tests for ``GET /api/v1/components/{id}``."""

from __future__ import annotations

from uuid import uuid4

import pytest
from httpx import AsyncClient

from app.domain.entities.component import Component

pytestmark = pytest.mark.integration


async def test_get_returns_component_when_found(
    api_client: AsyncClient,
    auth_headers: dict[str, str],
    seeded_component: Component,
) -> None:
    response = await api_client.get(
        f"/api/v1/components/{seeded_component.id}", headers=auth_headers
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["id"] == str(seeded_component.id)
    assert body["mpn"] == seeded_component.mpn


async def test_get_requires_authentication(
    api_client: AsyncClient, seeded_component: Component
) -> None:
    response = await api_client.get(f"/api/v1/components/{seeded_component.id}")
    assert response.status_code == 401


async def test_get_returns_404_when_missing(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    response = await api_client.get(f"/api/v1/components/{uuid4()}", headers=auth_headers)
    assert response.status_code == 404
    assert response.json()["code"] == "COMPONENT_NOT_FOUND"


async def test_get_with_garbage_id_returns_422(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    response = await api_client.get("/api/v1/components/not-a-uuid", headers=auth_headers)
    assert response.status_code == 422
