"""Integration tests for the secondary components endpoints.

Covers the supplier-prices / supplier-stocks / stock-events / parents /
projects-using sub-resources that don't have their own dedicated test file.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.domain.entities.component import Component

pytestmark = pytest.mark.integration


async def test_list_supplier_prices_empty(
    api_client: AsyncClient,
    auth_headers: dict[str, str],
    seeded_components_catalogue: list[Component],
) -> None:
    component = seeded_components_catalogue[0]
    response = await api_client.get(
        f"/api/v1/components/{component.id}/supplier-prices", headers=auth_headers
    )
    assert response.status_code == 200
    assert response.json() == []


async def test_list_supplier_prices_unknown_returns_404(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    response = await api_client.get(
        "/api/v1/components/00000000-0000-0000-0000-000000000000/supplier-prices",
        headers=auth_headers,
    )
    assert response.status_code == 404


async def test_list_supplier_stocks_empty(
    api_client: AsyncClient,
    auth_headers: dict[str, str],
    seeded_components_catalogue: list[Component],
) -> None:
    component = seeded_components_catalogue[0]
    response = await api_client.get(
        f"/api/v1/components/{component.id}/supplier-stocks", headers=auth_headers
    )
    assert response.status_code == 200
    assert response.json() == []


async def test_list_supplier_stocks_unknown_returns_404(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    response = await api_client.get(
        "/api/v1/components/00000000-0000-0000-0000-000000000000/supplier-stocks",
        headers=auth_headers,
    )
    assert response.status_code == 404


async def test_list_stock_events_empty(
    api_client: AsyncClient,
    auth_headers: dict[str, str],
    seeded_components_catalogue: list[Component],
) -> None:
    component = seeded_components_catalogue[0]
    response = await api_client.get(
        f"/api/v1/components/{component.id}/stock-events", headers=auth_headers
    )
    assert response.status_code == 200
    body = response.json()
    assert body["items"] == []
    assert body["total"] == 0


async def test_list_stock_events_unknown_returns_404(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    response = await api_client.get(
        "/api/v1/components/00000000-0000-0000-0000-000000000000/stock-events",
        headers=auth_headers,
    )
    assert response.status_code == 404


async def test_list_component_parents_empty(
    api_client: AsyncClient,
    auth_headers: dict[str, str],
    seeded_components_catalogue: list[Component],
) -> None:
    component = seeded_components_catalogue[0]
    response = await api_client.get(
        f"/api/v1/components/{component.id}/parents", headers=auth_headers
    )
    assert response.status_code == 200
    assert response.json() == []


async def test_list_component_parents_returns_referencing_modules(
    api_client: AsyncClient,
    auth_headers: dict[str, str],
    seeded_components_catalogue: list[Component],
) -> None:
    component = seeded_components_catalogue[0]
    # Create a module and add the component as a child.
    module_response = await api_client.post(
        "/api/v1/modules",
        headers=auth_headers,
        json={"sku": "MOD-PAR-001", "name": "Parent module"},
    )
    assert module_response.status_code == 201
    module_id = module_response.json()["id"]
    add_child = await api_client.post(
        f"/api/v1/modules/{module_id}/children",
        headers=auth_headers,
        json={"child_component_id": str(component.id), "quantity": 1},
    )
    assert add_child.status_code == 201

    parents = await api_client.get(
        f"/api/v1/components/{component.id}/parents", headers=auth_headers
    )
    assert parents.status_code == 200
    rows = parents.json()
    assert len(rows) == 1
    assert rows[0]["sku"] == "MOD-PAR-001"


async def test_list_component_parents_unknown_returns_404(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    response = await api_client.get(
        "/api/v1/components/00000000-0000-0000-0000-000000000000/parents",
        headers=auth_headers,
    )
    assert response.status_code == 404


async def test_list_nato_scorings_empty_when_none_classified(
    api_client: AsyncClient,
    auth_headers: dict[str, str],
    seeded_components_catalogue: list[Component],
) -> None:
    component = seeded_components_catalogue[0]
    response = await api_client.get(
        f"/api/v1/components/{component.id}/nato-scorings", headers=auth_headers
    )
    assert response.status_code == 200
    assert response.json() == []


async def test_list_nato_scorings_unknown_returns_404(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    response = await api_client.get(
        "/api/v1/components/00000000-0000-0000-0000-000000000000/nato-scorings",
        headers=auth_headers,
    )
    assert response.status_code == 404
