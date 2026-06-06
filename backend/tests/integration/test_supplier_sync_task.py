"""End-to-end integration test for `_run_for_supplier` against a real DB.

We use a fake adapter (no HTTP) but the entire DB write path is real:

- `supplier_sync_runs` row created with status=running, finalised at end
- `suppliers` row auto-created for the supplier code
- `supplier_prices` rows upserted across the 4 fixed tiers
- `supplier_stocks` row inserted with today's snapshot
- `components.last_supplier_sync_at` updated
- `supplier_sync_errors` rows produced when the adapter raises
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core.exceptions import SupplierTransportError
from app.domain.entities.component import Component
from app.domain.entities.supplier_quote import (
    SupplierCode,
    SupplierPriceBreak,
    SupplierQuote,
)
from app.infrastructure.db.models.supplier import SupplierModel
from app.infrastructure.db.models.supplier_price import SupplierPriceModel
from app.infrastructure.db.models.supplier_stock import SupplierStockModel
from app.infrastructure.db.models.supplier_sync_error import SupplierSyncErrorModel
from app.infrastructure.db.models.supplier_sync_run import SupplierSyncRunModel
from app.infrastructure.db.session import get_session_factory
from app.infrastructure.repositories.component_repository import (
    SqlAlchemyComponentRepository,
)
from app.infrastructure.tasks.supplier_sync import _run_for_supplier

pytestmark = pytest.mark.asyncio


class _FakeAdapter:
    """In-process stand-in for a real adapter — drives the sync task
    without any HTTP layer."""

    def __init__(
        self,
        code: SupplierCode,
        quotes_by_mpn: dict[str, SupplierQuote | Exception],
    ) -> None:
        self.code = code
        self._quotes = quotes_by_mpn

    async def fetch_by_mpn(self, mpn: str) -> SupplierQuote | None:
        outcome = self._quotes.get(mpn)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome  # may be a SupplierQuote or None


def _quote_with_full_ladder(mpn: str) -> SupplierQuote:
    return SupplierQuote(
        supplier="mouser",
        mpn=mpn,
        manufacturer="Test Vendor",
        name="Test Component",
        description="Integration test fixture",
        family_hint="Sensors",
        datasheet_url="https://example.com/ds.pdf",
        package="SOIC-8",
        stock=4321,
        price_breaks=(
            SupplierPriceBreak(
                quantity=1,
                price_original=Decimal("0.42"),
                currency_original="EUR",
                price_eur=Decimal("0.42"),
            ),
            SupplierPriceBreak(
                quantity=10,
                price_original=Decimal("0.36"),
                currency_original="EUR",
                price_eur=Decimal("0.36"),
            ),
            SupplierPriceBreak(
                quantity=100,
                price_original=Decimal("0.28"),
                currency_original="EUR",
                price_eur=Decimal("0.28"),
            ),
            SupplierPriceBreak(
                quantity=1000,
                price_original=Decimal("0.22"),
                currency_original="EUR",
                price_eur=Decimal("0.22"),
            ),
        ),
        supplier_sku="TEST-SKU-1",
        supplier_product_url="https://example.com/p/test",
        last_seen_at=datetime.now(timezone.utc),
    )


async def _seed_component(*, mpn: str, name: str) -> UUID:
    factory = get_session_factory()
    async with factory() as session:
        repo = SqlAlchemyComponentRepository(session)
        comp = Component(
            mpn=mpn,
            name=name,
            family="Sensors",
            stock=0,
            tier=3,
            nato_score="B",
        )
        saved = await repo.save(comp)
        await session.commit()
        return saved.id


async def test_run_for_supplier_persists_history_and_finalises_success(
    api_client: AsyncClient,  # noqa: ARG001 — pulls in the autouse truncate fixture
) -> None:
    mpn = "TEST-SYNC-HAPPY"
    component_id = await _seed_component(mpn=mpn, name="Happy Test Component")
    adapter = _FakeAdapter("mouser", {mpn: _quote_with_full_ladder(mpn)})

    run_id = await _run_for_supplier(adapter, component_ids=[component_id])

    factory = get_session_factory()
    async with factory() as session:
        run = await session.get(SupplierSyncRunModel, run_id)
        assert run is not None
        assert run.status == "success"
        assert run.components_processed == 1
        assert run.components_updated == 1
        assert run.errors_count == 0
        assert run.finished_at is not None

        # Supplier row auto-created.
        suppliers = (
            await session.execute(
                select(SupplierModel).where(SupplierModel.name.ilike("Mouser"))
            )
        ).scalars().all()
        assert len(suppliers) == 1
        supplier_id = suppliers[0].id

        # 4 price tiers written for today.
        today = date.today()
        prices = (
            await session.execute(
                select(SupplierPriceModel)
                .where(SupplierPriceModel.component_id == component_id)
                .where(SupplierPriceModel.supplier_id == supplier_id)
                .where(SupplierPriceModel.valid_from == today)
                .order_by(SupplierPriceModel.qty_tier.asc())
            )
        ).scalars().all()
        assert [p.qty_tier for p in prices] == [1, 10, 100, 1000]
        assert prices[0].price == Decimal("0.4200")
        assert prices[2].price == Decimal("0.2800")

        # Stock snapshot inserted for today.
        stock_rows = (
            await session.execute(
                select(SupplierStockModel)
                .where(SupplierStockModel.component_id == component_id)
                .where(SupplierStockModel.supplier_id == supplier_id)
                .where(SupplierStockModel.snapshot_at == today)
            )
        ).scalars().all()
        assert len(stock_rows) == 1
        assert stock_rows[0].quantity == 4321


async def test_run_for_supplier_records_typed_error_and_finalises_partial(
    api_client: AsyncClient,  # noqa: ARG001
) -> None:
    happy_mpn = "TEST-SYNC-OK"
    bad_mpn = "TEST-SYNC-BAD"
    happy_id = await _seed_component(mpn=happy_mpn, name="Happy")
    bad_id = await _seed_component(mpn=bad_mpn, name="Broken")

    adapter = _FakeAdapter(
        "mouser",
        {
            happy_mpn: _quote_with_full_ladder(happy_mpn),
            bad_mpn: SupplierTransportError("simulated 5xx"),
        },
    )

    run_id = await _run_for_supplier(
        adapter, component_ids=[happy_id, bad_id]
    )

    factory = get_session_factory()
    async with factory() as session:
        run = await session.get(SupplierSyncRunModel, run_id)
        assert run is not None
        assert run.status == "partial"
        assert run.components_processed == 2
        assert run.components_updated == 1
        assert run.errors_count == 1

        errors = (
            await session.execute(
                select(SupplierSyncErrorModel).where(
                    SupplierSyncErrorModel.run_id == run_id
                )
            )
        ).scalars().all()
        assert len(errors) == 1
        assert errors[0].component_id == bad_id
        assert errors[0].error_code == "HTTP_5XX"
        assert "simulated" in errors[0].error_message


async def test_run_for_supplier_handles_none_quote_without_writing(
    api_client: AsyncClient,  # noqa: ARG001
) -> None:
    """When the adapter returns None (supplier has no record of this MPN),
    no price/stock rows are written and the run counters reflect that."""

    mpn = "TEST-SYNC-MISS"
    component_id = await _seed_component(mpn=mpn, name="Unknown Component")
    adapter = _FakeAdapter("mouser", {mpn: None})

    run_id = await _run_for_supplier(adapter, component_ids=[component_id])

    factory = get_session_factory()
    async with factory() as session:
        run = await session.get(SupplierSyncRunModel, run_id)
        assert run is not None
        # Processed=1 (we tried), updated=0 (no write because the adapter
        # returned None), errors=0 (no exception).
        assert run.components_processed == 1
        assert run.components_updated == 0
        assert run.errors_count == 0
        assert run.status == "success"

        prices = (
            await session.execute(
                select(SupplierPriceModel).where(
                    SupplierPriceModel.component_id == component_id
                )
            )
        ).scalars().all()
        assert len(prices) == 0


async def test_same_day_re_run_overwrites_prices_via_upsert(
    api_client: AsyncClient,  # noqa: ARG001
) -> None:
    """Two consecutive syncs on the same day MUST collapse to a single
    `(component, supplier, qty_tier, valid_from)` row per tier — the
    unique constraint is honoured via INSERT ... ON CONFLICT."""

    mpn = "TEST-SYNC-IDEMP"
    component_id = await _seed_component(mpn=mpn, name="Idempotent")

    cheap = _quote_with_full_ladder(mpn)
    expensive = SupplierQuote(
        supplier="mouser",
        mpn=mpn,
        price_breaks=(
            SupplierPriceBreak(
                quantity=100,
                price_original=Decimal("99.99"),
                currency_original="EUR",
                price_eur=Decimal("99.99"),
            ),
        ),
        stock=12345,
        last_seen_at=datetime.now(timezone.utc),
    )

    await _run_for_supplier(
        _FakeAdapter("mouser", {mpn: cheap}),
        component_ids=[component_id],
    )
    await _run_for_supplier(
        _FakeAdapter("mouser", {mpn: expensive}),
        component_ids=[component_id],
    )

    factory = get_session_factory()
    async with factory() as session:
        today = date.today()
        prices = (
            await session.execute(
                select(SupplierPriceModel)
                .where(SupplierPriceModel.component_id == component_id)
                .where(SupplierPriceModel.valid_from == today)
                .where(SupplierPriceModel.qty_tier == 100)
            )
        ).scalars().all()
        assert len(prices) == 1
        # Second run's price wins.
        assert prices[0].price == Decimal("99.9900")

        stock_rows = (
            await session.execute(
                select(SupplierStockModel)
                .where(SupplierStockModel.component_id == component_id)
                .where(SupplierStockModel.snapshot_at == today)
            )
        ).scalars().all()
        assert len(stock_rows) == 1
        assert stock_rows[0].quantity == 12345
