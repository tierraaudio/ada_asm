"""Integration tests for ``DELETE /api/v1/components/{id}``."""

from __future__ import annotations

from uuid import uuid4

import pytest
from httpx import AsyncClient

from app.domain.entities.component import Component

pytestmark = pytest.mark.integration


async def test_delete_returns_204_and_removes_the_component(
    api_client: AsyncClient,
    auth_headers: dict[str, str],
    seeded_component: Component,
) -> None:
    response = await api_client.delete(
        f"/api/v1/components/{seeded_component.id}", headers=auth_headers
    )
    assert response.status_code == 204, response.text
    # Verify subsequent GET is now 404.
    follow_up = await api_client.get(
        f"/api/v1/components/{seeded_component.id}", headers=auth_headers
    )
    assert follow_up.status_code == 404


async def test_delete_is_idempotent_on_missing_id(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    response = await api_client.delete(f"/api/v1/components/{uuid4()}", headers=auth_headers)
    assert response.status_code == 204


async def test_delete_requires_authentication(
    api_client: AsyncClient, seeded_component: Component
) -> None:
    response = await api_client.delete(f"/api/v1/components/{seeded_component.id}")
    assert response.status_code == 401
