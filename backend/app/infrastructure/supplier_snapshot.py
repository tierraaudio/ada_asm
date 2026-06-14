"""Map a `SupplierQuote` to `supplier_prices` + `supplier_stocks` rows.

Shared by the daily supplier sync (`infrastructure/tasks/supplier_sync.py`)
and the component ingestion service (so a freshly-ingested component carries
a first price/stock snapshot from day one instead of staying empty until the
next nightly sync). See change `ingest-component-from-mpn`.
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db.models.supplier import SupplierModel
from app.infrastructure.db.models.supplier_price import SupplierPriceModel
from app.infrastructure.db.models.supplier_stock import SupplierStockModel

if TYPE_CHECKING:
    from datetime import date

    from app.domain.entities.supplier_quote import SupplierCode, SupplierQuote

# Standardised qty tiers persisted in `supplier_prices`. The unique
# constraint on the table is keyed on (component, supplier, qty_tier,
# valid_from); these four values bound how many price rows a write can
# produce per (component, supplier, day).
QTY_TIERS: tuple[int, ...] = (1, 10, 100, 1000)

# Display names registered the first time we touch the `suppliers` table.
# Adapter `code` → human-readable name shown in the existing UI.
SUPPLIER_DISPLAY_NAMES: dict[str, str] = {
    "mouser": "Mouser",
    "digikey": "DigiKey",
    "tme": "TME",
    "farnell": "Farnell",
    "rs": "RS Online",
}


def pick_unit_price_for_tier(
    breaks: list[tuple[int, Decimal]],
    tier: int,
) -> Decimal | None:
    """Return the unit price applicable to a `tier`-unit order.

    `breaks` is a list of `(quantity, price_eur)` tuples already filtered
    to non-null EUR prices. We pick the break with the largest
    `quantity` not exceeding `tier`. None if every break starts above
    `tier` or `breaks` is empty.
    """

    applicable = [(q, p) for q, p in breaks if q <= tier]
    if not applicable:
        return None
    return max(applicable, key=lambda pair: pair[0])[1]


async def ensure_supplier_row(session: AsyncSession, code: SupplierCode) -> UUID:
    """Look up or insert the `suppliers` row for an adapter `code` and
    return its UUID. Names are case-insensitive (the table has a
    functional unique index on `lower(name)`)."""

    display_name = SUPPLIER_DISPLAY_NAMES.get(code, code.capitalize())
    existing = await session.execute(
        select(SupplierModel.id).where(
            SupplierModel.name.ilike(display_name),
        )
    )
    row_id = existing.scalar_one_or_none()
    if row_id is not None:
        return row_id

    new_id = uuid4()
    session.add(SupplierModel(id=new_id, name=display_name))
    await session.flush()
    return new_id


async def upsert_prices_and_stock(
    session: AsyncSession,
    *,
    component_id: UUID,
    supplier_id: UUID,
    quote: SupplierQuote,
    today: date,
) -> bool:
    """Map a `SupplierQuote` to the existing `supplier_prices` (4 tiers)
    + `supplier_stocks` rows. Returns True iff at least one row was
    written (i.e. the quote contributed real data)."""

    eur_breaks: list[tuple[int, Decimal]] = [
        (pb.quantity, pb.price_eur) for pb in quote.price_breaks if pb.price_eur is not None
    ]

    wrote_anything = False

    if eur_breaks:
        for tier in QTY_TIERS:
            unit_price = pick_unit_price_for_tier(eur_breaks, tier)
            if unit_price is None:
                continue
            stmt = pg_insert(SupplierPriceModel).values(
                id=uuid4(),
                component_id=component_id,
                supplier_id=supplier_id,
                qty_tier=tier,
                price=unit_price,
                valid_from=today,
            )
            stmt = stmt.on_conflict_do_update(
                constraint="uq_supplier_prices_component_supplier_qty_valid_from",
                set_={"price": unit_price},
            )
            await session.execute(stmt)
            wrote_anything = True

    if quote.stock is not None:
        stmt = pg_insert(SupplierStockModel).values(
            id=uuid4(),
            component_id=component_id,
            supplier_id=supplier_id,
            quantity=int(quote.stock),
            snapshot_at=today,
        )
        stmt = stmt.on_conflict_do_update(
            constraint="uq_supplier_stocks_component_supplier_snapshot",
            set_={"quantity": int(quote.stock)},
        )
        await session.execute(stmt)
        wrote_anything = True

    return wrote_anything
