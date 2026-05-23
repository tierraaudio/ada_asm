"""Integration tests for ``PATCH /api/v1/components/{id}``."""

from __future__ import annotations

from uuid import uuid4

import pytest
from httpx import AsyncClient

from app.domain.entities.component import Component

pytestmark = pytest.mark.integration


async def test_patch_partial_update_only_touches_provided_fields(
    api_client: AsyncClient,
    auth_headers: dict[str, str],
    seeded_component: Component,
) -> None:
    response = await api_client.patch(
        f"/api/v1/components/{seeded_component.id}",
        json={"name": "Renamed"},
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["name"] == "Renamed"
    # Untouched fields preserved
    assert body["family"] == seeded_component.family
    assert body["tier"] == seeded_component.tier
    assert body["sku"] == seeded_component.sku


async def test_patch_can_clear_nullable_field(
    api_client: AsyncClient,
    auth_headers: dict[str, str],
    seeded_component: Component,
) -> None:
    response = await api_client.patch(
        f"/api/v1/components/{seeded_component.id}",
        json={"description": None},
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text
    assert response.json()["description"] is None


async def test_patch_ignores_mpn_field_attempt(
    api_client: AsyncClient,
    auth_headers: dict[str, str],
    seeded_component: Component,
) -> None:
    """`mpn` is silently ignored by ConfigDict(extra='ignore')."""
    response = await api_client.patch(
        f"/api/v1/components/{seeded_component.id}",
        json={"mpn": "CANNOT-CHANGE", "name": "newname"},
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["mpn"] == seeded_component.mpn
    assert body["name"] == "newname"


async def test_patch_requires_authentication(
    api_client: AsyncClient, seeded_component: Component
) -> None:
    response = await api_client.patch(
        f"/api/v1/components/{seeded_component.id}", json={"name": "x"}
    )
    assert response.status_code == 401


async def test_patch_returns_404_for_unknown_id(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    response = await api_client.patch(
        f"/api/v1/components/{uuid4()}",
        json={"name": "x"},
        headers=auth_headers,
    )
    assert response.status_code == 404
    assert response.json()["code"] == "COMPONENT_NOT_FOUND"


async def test_patch_rejects_invalid_tier(
    api_client: AsyncClient,
    auth_headers: dict[str, str],
    seeded_component: Component,
) -> None:
    response = await api_client.patch(
        f"/api/v1/components/{seeded_component.id}",
        json={"tier": "Z"},
        headers=auth_headers,
    )
    assert response.status_code == 422


async def test_patch_rejects_negative_stock(
    api_client: AsyncClient,
    auth_headers: dict[str, str],
    seeded_component: Component,
) -> None:
    response = await api_client.patch(
        f"/api/v1/components/{seeded_component.id}",
        json={"stock": -5},
        headers=auth_headers,
    )
    assert response.status_code == 422


async def test_patch_with_empty_body_is_a_no_op(
    api_client: AsyncClient,
    auth_headers: dict[str, str],
    seeded_component: Component,
) -> None:
    response = await api_client.patch(
        f"/api/v1/components/{seeded_component.id}",
        json={},
        headers=auth_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["mpn"] == seeded_component.mpn
    assert body["name"] == seeded_component.name
