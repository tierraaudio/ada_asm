"""Integration tests for ``POST /api/v1/components``."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.domain.entities.component import Component

pytestmark = pytest.mark.integration


def _payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "mpn": "NEW-MPN-001",
        "name": "Componente nuevo",
        "family": "Sensores",
        "tier": 2,
        "nato_score": "A",
        "sku": "NEW-SKU",
        "description": "desc",
        "datasheet_url": "https://example.com/ds.pdf",
        "location": "G-N-99",
        "fabricante": "Acme",
        "tipo_almacenamiento": "Gaveta",
        "stock": 10,
        "stock_min": 4,
        "country_of_origin": "US",
    }
    payload.update(overrides)
    return payload


async def test_create_happy_path_returns_201(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    response = await api_client.post("/api/v1/components", json=_payload(), headers=auth_headers)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["mpn"] == "NEW-MPN-001"
    assert body["tier"] == 2
    assert body["nato_score"] == "A"
    assert body["fabricante"] == "Acme"


async def test_create_requires_authentication(api_client: AsyncClient) -> None:
    response = await api_client.post("/api/v1/components", json=_payload())
    assert response.status_code == 401


async def test_create_with_minimal_payload(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    minimal = {
        "mpn": "MIN-001",
        "name": "min",
        "family": "Discretos",
        "tier": 4,
        "nato_score": "C",
    }
    response = await api_client.post("/api/v1/components", json=minimal, headers=auth_headers)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["sku"] is None
    assert body["stock"] == 0
    assert body["stock_min"] is None


async def test_create_duplicate_mpn_returns_409(
    api_client: AsyncClient,
    auth_headers: dict[str, str],
    seeded_component: Component,
) -> None:
    response = await api_client.post(
        "/api/v1/components",
        json=_payload(mpn=seeded_component.mpn),
        headers=auth_headers,
    )
    assert response.status_code == 409
    assert response.json()["code"] == "MPN_ALREADY_REGISTERED"


async def test_create_duplicate_mpn_case_insensitive(
    api_client: AsyncClient,
    auth_headers: dict[str, str],
    seeded_component: Component,
) -> None:
    response = await api_client.post(
        "/api/v1/components",
        json=_payload(mpn=seeded_component.mpn.lower()),
        headers=auth_headers,
    )
    assert response.status_code == 409


async def test_create_rejects_invalid_tier(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    response = await api_client.post(
        "/api/v1/components", json=_payload(tier=99), headers=auth_headers
    )
    assert response.status_code == 422


async def test_create_rejects_invalid_nato_score(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    response = await api_client.post(
        "/api/v1/components", json=_payload(nato_score="ZZ"), headers=auth_headers
    )
    assert response.status_code == 422


async def test_create_rejects_lowercase_country_code(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    response = await api_client.post(
        "/api/v1/components",
        json=_payload(country_of_origin="us"),
        headers=auth_headers,
    )
    assert response.status_code == 422


async def test_create_rejects_negative_stock(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    response = await api_client.post(
        "/api/v1/components", json=_payload(stock=-1), headers=auth_headers
    )
    assert response.status_code == 422


async def test_create_rejects_empty_mpn(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    response = await api_client.post(
        "/api/v1/components", json=_payload(mpn=""), headers=auth_headers
    )
    assert response.status_code == 422
