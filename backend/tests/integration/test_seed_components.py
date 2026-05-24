"""Integration tests for ``python -m app.scripts.seed_components``."""

from __future__ import annotations

import pytest
from sqlalchemy import func, select

from app.infrastructure.db.models.component import ComponentModel
from app.infrastructure.db.models.stock_event import StockEventModel
from app.infrastructure.db.models.supplier import SupplierModel
from app.infrastructure.db.models.supplier_price import SupplierPriceModel
from app.infrastructure.db.models.supplier_stock import SupplierStockModel
from app.infrastructure.db.session import get_session_factory
from app.scripts import seed_components as seed_module

pytestmark = pytest.mark.integration


async def _count(table: type) -> int:
    factory = get_session_factory()
    async with factory() as session:
        return int((await session.execute(select(func.count(table.id)))).scalar_one())


async def test_seed_inserts_components_suppliers_prices_stock_events() -> None:
    exit_code = await seed_module._seed(reset=False)
    assert exit_code == 0

    expected_components = len(seed_module.SAMPLE_COMPONENTS)
    expected_suppliers = len(seed_module.SUPPLIER_NAMES)

    assert await _count(ComponentModel) == expected_components
    assert await _count(SupplierModel) == expected_suppliers
    # Each component gets 4 snapshots (today + 2m + 4m + 6m ago) x 5 suppliers
    # x 4 qty_tiers -> 80 price rows per component.
    assert await _count(SupplierPriceModel) == expected_components * expected_suppliers * 4 * 4
    # 9 weekly snapshots per supplier per component.
    assert await _count(SupplierStockModel) == expected_components * expected_suppliers * 9
    # Each component gets 3-5 stock events.
    events = await _count(StockEventModel)
    assert events >= 3 * expected_components
    assert events <= 5 * expected_components


async def test_seed_refuses_to_reseed_when_components_exist() -> None:
    assert await seed_module._seed(reset=False) == 0
    assert await seed_module._seed(reset=False) == 2
    assert await _count(ComponentModel) == len(seed_module.SAMPLE_COMPONENTS)


async def test_seed_with_reset_truncates_and_reseeds() -> None:
    assert await seed_module._seed(reset=False) == 0
    first_events = await _count(StockEventModel)
    assert await seed_module._seed(reset=True) == 0
    assert await _count(ComponentModel) == len(seed_module.SAMPLE_COMPONENTS)
    # Deterministic seed → same event count after reset.
    assert await _count(StockEventModel) == first_events
