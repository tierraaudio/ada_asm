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
        "tier": "B",
        "nato_score": "otan",
        "sku": "NEW-SKU",
        "description": "desc",
        "datasheet_url": "https://example.com/ds.pdf",
        "location": "A-1",
        "supplier": "DigiKey",
        "price_per_100": "1.2345",
        "stock": 10,
        "country_of_origin": "US",
    }
    payload.update(overrides)
    return payload


async def test_create_happy_path_returns_201_and_persisted_body(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    response = await api_client.post(
        "/api/v1/components", json=_payload(), headers=auth_headers
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["mpn"] == "NEW-MPN-001"
    assert body["sku"] == "NEW-SKU"
    assert body["tier"] == "B"
    assert body["nato_score"] == "otan"
    assert body["country_of_origin"] == "US"
    assert "id" in body
    assert "created_at" in body
    assert "updated_at" in body


async def test_create_requires_authentication(api_client: AsyncClient) -> None:
    response = await api_client.post("/api/v1/components", json=_payload())
    assert response.status_code == 401
    assert response.json()["code"] == "UNAUTHENTICATED"


async def test_create_with_minimal_payload(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    minimal = {
        "mpn": "MIN-001",
        "name": "min",
        "family": "Discretos",
        "tier": "D",
        "nato_score": "neutral",
    }
    response = await api_client.post(
        "/api/v1/components", json=minimal, headers=auth_headers
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["sku"] is None
    assert body["stock"] == 0
    assert body["price_per_100"] is None


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
    body = response.json()
    assert body["code"] == "MPN_ALREADY_REGISTERED"


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
    assert response.json()["code"] == "MPN_ALREADY_REGISTERED"


async def test_create_rejects_invalid_tier(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    response = await api_client.post(
        "/api/v1/components", json=_payload(tier="Z"), headers=auth_headers
    )
    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"


async def test_create_rejects_invalid_nato_score(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    response = await api_client.post(
        "/api/v1/components", json=_payload(nato_score="garbage"), headers=auth_headers
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
