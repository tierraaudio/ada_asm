"""Integration tests for ``GET /api/v1/components/{id}/purchases``."""

from __future__ import annotations

from uuid import uuid4

import pytest
from httpx import AsyncClient

from app.domain.entities.component import Component

pytestmark = pytest.mark.integration


async def test_purchases_lists_seeded_rows_ordered_newest_first(
    api_client: AsyncClient,
    auth_headers: dict[str, str],
    seeded_component_with_purchases: Component,
) -> None:
    response = await api_client.get(
        f"/api/v1/components/{seeded_component_with_purchases.id}/purchases",
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total"] == 3
    dates = [item["purchased_at"] for item in body["items"]]
    assert dates == sorted(dates, reverse=True)


async def test_purchases_404s_when_component_missing(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    response = await api_client.get(
        f"/api/v1/components/{uuid4()}/purchases", headers=auth_headers
    )
    assert response.status_code == 404
    assert response.json()["code"] == "COMPONENT_NOT_FOUND"


async def test_purchases_requires_authentication(
    api_client: AsyncClient, seeded_component_with_purchases: Component
) -> None:
    response = await api_client.get(
        f"/api/v1/components/{seeded_component_with_purchases.id}/purchases"
    )
    assert response.status_code == 401


async def test_purchases_pagination_returns_partial_page(
    api_client: AsyncClient,
    auth_headers: dict[str, str],
    seeded_component_with_purchases: Component,
) -> None:
    response = await api_client.get(
        f"/api/v1/components/{seeded_component_with_purchases.id}/purchases"
        "?page=1&page_size=2",
        headers=auth_headers,
    )
    body = response.json()
    assert body["total"] == 3
    assert len(body["items"]) == 2
    assert body["page_size"] == 2


async def test_purchases_returns_empty_list_when_none(
    api_client: AsyncClient,
    auth_headers: dict[str, str],
    seeded_component: Component,
) -> None:
    response = await api_client.get(
        f"/api/v1/components/{seeded_component.id}/purchases", headers=auth_headers
    )
    assert response.status_code == 200
    assert response.json() == {"items": [], "total": 0, "page": 1, "page_size": 25}
