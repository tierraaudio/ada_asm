"""Integration tests for ``POST /api/v1/components/{id}/sync`` (placeholder)."""

from __future__ import annotations

from uuid import uuid4

import pytest
from httpx import AsyncClient

from app.domain.entities.component import Component

pytestmark = pytest.mark.integration


async def test_sync_returns_202_queued_for_existing_component(
    api_client: AsyncClient,
    auth_headers: dict[str, str],
    seeded_component: Component,
) -> None:
    response = await api_client.post(
        f"/api/v1/components/{seeded_component.id}/sync", headers=auth_headers
    )
    assert response.status_code == 202, response.text
    assert response.json() == {"status": "queued"}


async def test_sync_404s_when_component_missing(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    response = await api_client.post(
        f"/api/v1/components/{uuid4()}/sync", headers=auth_headers
    )
    assert response.status_code == 404
    assert response.json()["code"] == "COMPONENT_NOT_FOUND"


async def test_sync_requires_authentication(
    api_client: AsyncClient, seeded_component: Component
) -> None:
    response = await api_client.post(f"/api/v1/components/{seeded_component.id}/sync")
    assert response.status_code == 401
