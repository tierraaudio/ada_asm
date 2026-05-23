"""Integration tests for ``GET /api/v1/components``."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.domain.entities.component import Component

pytestmark = pytest.mark.integration


async def test_list_returns_empty_page_when_no_components(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    response = await api_client.get("/api/v1/components", headers=auth_headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body == {"items": [], "total": 0, "page": 1, "page_size": 25}


async def test_list_requires_authentication(api_client: AsyncClient) -> None:
    response = await api_client.get("/api/v1/components")
    assert response.status_code == 401
    assert response.json()["code"] == "UNAUTHENTICATED"


async def test_list_returns_all_seeded_components(
    api_client: AsyncClient,
    auth_headers: dict[str, str],
    seeded_components_catalogue: list[Component],
) -> None:
    response = await api_client.get("/api/v1/components", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == len(seeded_components_catalogue)
    mpns = {item["mpn"] for item in body["items"]}
    assert mpns == {c.mpn for c in seeded_components_catalogue}


async def test_list_search_q_is_case_insensitive_on_mpn(
    api_client: AsyncClient,
    auth_headers: dict[str, str],
    seeded_components_catalogue: list[Component],
) -> None:
    response = await api_client.get(
        "/api/v1/components?q=acs712", headers=auth_headers
    )
    assert response.status_code == 200
    mpns = [item["mpn"] for item in response.json()["items"]]
    assert mpns == ["ACS712"]


async def test_list_search_q_matches_sku(
    api_client: AsyncClient,
    auth_headers: dict[str, str],
    seeded_components_catalogue: list[Component],
) -> None:
    response = await api_client.get(
        "/api/v1/components?q=ENV", headers=auth_headers
    )
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["mpn"] == "BME280"


async def test_list_search_q_matches_name(
    api_client: AsyncClient,
    auth_headers: dict[str, str],
    seeded_components_catalogue: list[Component],
) -> None:
    response = await api_client.get(
        "/api/v1/components?q=timer", headers=auth_headers
    )
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["mpn"] == "NE555"


async def test_list_search_q_matches_family(
    api_client: AsyncClient,
    auth_headers: dict[str, str],
    seeded_components_catalogue: list[Component],
) -> None:
    response = await api_client.get(
        "/api/v1/components?q=microcontroladores", headers=auth_headers
    )
    body = response.json()
    assert body["total"] == 2
    assert {it["mpn"] for it in body["items"]} == {"ESP32-WROOM-32E", "STM32F407VGT6"}


async def test_list_filter_family_exact_match(
    api_client: AsyncClient,
    auth_headers: dict[str, str],
    seeded_components_catalogue: list[Component],
) -> None:
    response = await api_client.get(
        "/api/v1/components?family=Sensores", headers=auth_headers
    )
    body = response.json()
    assert body["total"] == 2
    assert {it["family"] for it in body["items"]} == {"Sensores"}


async def test_list_filter_supplier(
    api_client: AsyncClient,
    auth_headers: dict[str, str],
    seeded_components_catalogue: list[Component],
) -> None:
    response = await api_client.get(
        "/api/v1/components?supplier=Mouser", headers=auth_headers
    )
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["mpn"] == "ESP32-WROOM-32E"


async def test_list_filter_tier(
    api_client: AsyncClient,
    auth_headers: dict[str, str],
    seeded_components_catalogue: list[Component],
) -> None:
    response = await api_client.get(
        "/api/v1/components?tier=A%2B", headers=auth_headers
    )
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["mpn"] == "STM32F407VGT6"


async def test_list_filter_nato_score(
    api_client: AsyncClient,
    auth_headers: dict[str, str],
    seeded_components_catalogue: list[Component],
) -> None:
    response = await api_client.get(
        "/api/v1/components?nato_score=100_otan", headers=auth_headers
    )
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["mpn"] == "NE555"


async def test_list_pagination_page_1(
    api_client: AsyncClient,
    auth_headers: dict[str, str],
    seeded_components_catalogue: list[Component],
) -> None:
    response = await api_client.get(
        "/api/v1/components?page=1&page_size=2", headers=auth_headers
    )
    body = response.json()
    assert body["total"] == 5
    assert body["page"] == 1
    assert body["page_size"] == 2
    assert len(body["items"]) == 2


async def test_list_pagination_page_beyond_total_returns_empty_items(
    api_client: AsyncClient,
    auth_headers: dict[str, str],
    seeded_components_catalogue: list[Component],
) -> None:
    response = await api_client.get(
        "/api/v1/components?page=99&page_size=2", headers=auth_headers
    )
    body = response.json()
    assert body["total"] == 5
    assert body["items"] == []


async def test_list_rejects_page_size_above_100(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    response = await api_client.get(
        "/api/v1/components?page_size=500", headers=auth_headers
    )
    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"


async def test_list_rejects_page_below_one(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    response = await api_client.get(
        "/api/v1/components?page=0", headers=auth_headers
    )
    assert response.status_code == 422


async def test_list_rejects_invalid_tier(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    response = await api_client.get(
        "/api/v1/components?tier=Z", headers=auth_headers
    )
    assert response.status_code == 422
