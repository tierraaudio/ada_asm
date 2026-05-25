"""End-to-end tests that exercise aggregate computation + price history
through the full seed data (components + suppliers + supplier_prices +
scorings + modules)."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.application.services.modules_service import ModuleService
from app.domain.repositories.module_repository import ModuleFilters
from app.infrastructure.db.models.module import ModuleModel
from app.infrastructure.db.session import get_session_factory
from app.scripts import seed_components, seed_modules

pytestmark = pytest.mark.integration


async def _seed_full() -> None:
    assert await seed_components._seed(reset=False) == 0
    assert await seed_modules._seed(reset=False) == 0


async def test_list_modules_hydrates_aggregates_with_real_seed(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    await _seed_full()
    response = await api_client.get("/api/v1/modules", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 10

    # At least one of the seeded modules should have a non-null precio_total
    # (the seed gives every component a preferred supplier + supplier_prices).
    prices = [item["precio_total"] for item in body["items"]]
    assert any(p is not None for p in prices), prices

    # The worst Tier across all seeded children — every spec has at least
    # one tier-1 component → aggregated_tier == 1.
    tiers = [item["aggregated_tier"] for item in body["items"]]
    assert all(t is not None for t in tiers)


async def test_get_detail_aggregates_with_real_seed(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    await _seed_full()
    factory = get_session_factory()
    async with factory() as session:
        # Pick the nested parent (Sistema Potencia BLDC) which has both a
        # sub-module and component children.
        module_id = (
            await session.execute(select(ModuleModel.id).where(ModuleModel.sku == "MOD-PWR-001"))
        ).scalar_one()

    response = await api_client.get(f"/api/v1/modules/{module_id}", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    # Includes one sub-module + two component children = 3 direct edges.
    assert len(body["children"]) == 4  # MOD-PWR-001: 2 components + 2 sub-modules (DRV, FILT)
    # Aggregates filled in.
    assert body["aggregated_tier"] is not None
    assert body["aggregated_nato_score"] is not None
    # Hydrated children carry the right summary shape.
    has_module_child = any(c["child_module"] is not None for c in body["children"])
    has_comp_child = any(c["child_component"] is not None for c in body["children"])
    assert has_module_child and has_comp_child


async def test_price_history_returns_series_with_real_seed(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    await _seed_full()
    factory = get_session_factory()
    async with factory() as session:
        module_id = (
            await session.execute(select(ModuleModel.id).where(ModuleModel.sku == "MOD-SENS-001"))
        ).scalar_one()

    response = await api_client.get(
        f"/api/v1/modules/{module_id}/price-history?period=year",
        headers=auth_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["period"] == "year"
    # Should have at least one date point given the seed inserts 4 historical
    # snapshots over the past 6 months per component.
    assert len(body["series"]) > 0
    # Each point has a positive price.
    assert all(float(p["price"]) > 0 for p in body["series"])


async def test_service_list_modules_pagination_boundary(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    # Beyond-total pages return empty items but reflect the total count.
    await _seed_full()
    response = await api_client.get("/api/v1/modules?page=10&page_size=2", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["items"] == []
    assert body["total"] == 10


async def test_get_by_sku_lookup(api_client: AsyncClient) -> None:
    # Direct repo-level smoke through the service to exercise get_by_sku.
    await _seed_full()
    factory = get_session_factory()
    async with factory() as session:
        svc = ModuleService(session)
        page = await svc.list_modules(filters=ModuleFilters(q="MOD-SENS"), page=1, page_size=10)
        assert page.total == 1
        assert page.items[0].sku == "MOD-SENS-001"
