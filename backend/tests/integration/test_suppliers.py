"""Integration tests for ``GET /api/v1/suppliers``."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.domain.entities.supplier import Supplier

pytestmark = pytest.mark.integration


async def test_list_suppliers_requires_authentication(api_client: AsyncClient) -> None:
    response = await api_client.get("/api/v1/suppliers")
    assert response.status_code == 401


async def test_list_suppliers_returns_seeded_rows(
    api_client: AsyncClient,
    auth_headers: dict[str, str],
    seeded_suppliers: dict[str, Supplier],
) -> None:
    response = await api_client.get("/api/v1/suppliers", headers=auth_headers)
    assert response.status_code == 200, response.text
    names = [s["name"] for s in response.json()]
    assert set(names) == {"DigiKey", "Mouser", "Farnell", "RS", "TME"}


async def test_list_suppliers_empty_when_unseeded(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    response = await api_client.get("/api/v1/suppliers", headers=auth_headers)
    assert response.status_code == 200
    assert response.json() == []
