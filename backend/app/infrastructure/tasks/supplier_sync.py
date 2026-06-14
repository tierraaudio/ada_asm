"""Daily supplier sync — Celery tasks.

Architecture (simpler than the spec's `chord` design — one task per
supplier loops all components sequentially; cross-supplier parallelism
is achieved by enqueuing one task per supplier):

    run_daily_sync()                  ← Beat-triggered orchestrator
        └─> sync_one_supplier.delay(code) per enabled supplier  (parallel)
            └─> creates supplier_sync_runs row (status='running')
            └─> for each component:
                  fetch_by_mpn → upsert supplier_prices (4 tiers) +
                                  insert supplier_stocks snapshot +
                                  update components.last_supplier_sync_at
                  on SupplierError → insert supplier_sync_errors row
            └─> updates run row with totals + status

Async work runs inside `asyncio.run(...)` because Celery worker processes
are sync. Each task opens its own SQLAlchemy AsyncSession against the
existing `get_session_factory()`.

Tier mapping: each adapter returns arbitrary `price_breaks[]` (Mouser
may return qty 2000, DigiKey returns 1/10/50/100/250/500/1000/2500…).
We collapse these to the four fixed tiers `(1, 10, 100, 1000)` by, for
each tier T, picking the unit price from the break whose `quantity` is
the largest value ≤ T. Breaks above 1000 are ignored.

Idempotency: the unique constraint
`(component_id, supplier_id, qty_tier, valid_from)` means same-day
re-runs would conflict. The task uses `INSERT … ON CONFLICT DO UPDATE`
so a manual ad-hoc trigger on the same day overwrites the row instead of
failing. `supplier_stocks` has a similar `(component_id, supplier_id,
snapshot_at)` unique → same upsert pattern.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import SupplierError
from app.domain.entities.supplier_quote import SupplierQuote
from app.domain.repositories.supplier_adapter import SupplierAdapter
from app.infrastructure.celery_app import celery_app
from app.infrastructure.db.models.component import ComponentModel
from app.infrastructure.db.models.supplier import SupplierModel
from app.infrastructure.db.models.supplier_price import SupplierPriceModel
from app.infrastructure.db.models.supplier_stock import SupplierStockModel
from app.infrastructure.db.models.supplier_sync_error import SupplierSyncErrorModel
from app.infrastructure.db.models.supplier_sync_run import SupplierSyncRunModel
from app.infrastructure.db.session import (
    dispose_engine,
    forget_engine,
    get_session_factory,
)

if TYPE_CHECKING:
    from app.domain.entities.supplier_quote import SupplierCode

_log = logging.getLogger(__name__)

# Standardised qty tiers persisted in `supplier_prices`. The unique
# constraint on the table is keyed on (component, supplier, qty_tier,
# valid_from); these four values bound how many price rows a sync can
# produce per (component, supplier, day).
_QTY_TIERS: tuple[int, ...] = (1, 10, 100, 1000)

# Display names registered the first time we touch the `suppliers` table.
# Adapter `code` → human-readable name shown in the existing UI.
_SUPPLIER_DISPLAY_NAMES: dict[str, str] = {
    "mouser": "Mouser",
    "digikey": "DigiKey",
    "tme": "TME",
    "farnell": "Farnell",
    "rs": "RS Online",
}


def _pick_unit_price_for_tier(
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


async def _ensure_supplier_row(
    session: AsyncSession, code: SupplierCode
) -> UUID:
    """Look up or insert the `suppliers` row for an adapter `code` and
    return its UUID. Names are case-insensitive (the table has a
    functional unique index on `lower(name)`)."""

    display_name = _SUPPLIER_DISPLAY_NAMES.get(code, code.capitalize())
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


async def _upsert_prices_and_stock(
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
        (pb.quantity, pb.price_eur)
        for pb in quote.price_breaks
        if pb.price_eur is not None
    ]

    wrote_anything = False

    if eur_breaks:
        for tier in _QTY_TIERS:
            unit_price = _pick_unit_price_for_tier(eur_breaks, tier)
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


async def _record_error(
    session: AsyncSession,
    *,
    run_id: UUID,
    component_id: UUID,
    supplier: SupplierCode,
    error: SupplierError,
) -> None:
    error_code = getattr(error, "error_code", "UNKNOWN") or "UNKNOWN"
    session.add(
        SupplierSyncErrorModel(
            id=uuid4(),
            run_id=run_id,
            component_id=component_id,
            supplier=supplier,
            error_code=error_code,
            error_message=str(error)[:2000],
        )
    )


async def _create_run_row(
    session: AsyncSession, supplier: SupplierCode
) -> UUID:
    run_id = uuid4()
    session.add(
        SupplierSyncRunModel(
            id=run_id,
            supplier=supplier,
            status="running",
        )
    )
    await session.flush()
    await session.commit()
    return run_id


async def _finalise_run(
    session: AsyncSession,
    *,
    run_id: UUID,
    processed: int,
    updated: int,
    errors: int,
) -> None:
    if errors == 0 and processed > 0:
        status = "success"
    elif updated == 0 and errors > 0:
        status = "failed"
    elif errors > 0:
        status = "partial"
    else:
        # processed=0: empty catalogue → still "success" (nothing to do).
        status = "success"

    run = await session.get(SupplierSyncRunModel, run_id)
    if run is None:
        return
    run.finished_at = datetime.now(UTC)
    run.components_processed = processed
    run.components_updated = updated
    run.errors_count = errors
    run.status = status
    await session.commit()


async def _run_for_supplier(
    adapter: SupplierAdapter,
    *,
    component_ids: list[UUID] | None = None,
    existing_run_id: UUID | None = None,
) -> UUID:
    """End-to-end sync for one supplier. Used by the Celery task and by
    the ad-hoc `POST /supplier-sync/runs` trigger.

    `component_ids=None` means "all components in the catalogue". When
    provided, only those IDs are walked (used by tests to bound scope).

    `existing_run_id` lets the HTTP trigger pre-create the run row and
    return its ID to the operator before the Celery worker picks the
    task up. When None we create the row ourselves (the daily Beat
    path).

    Returns the `supplier_sync_runs.id` of the run row used.
    """

    factory = get_session_factory()
    today = datetime.now(UTC).date()
    processed = 0
    updated = 0
    errors = 0

    # First DB block: ensure run row exists + capture target component list.
    async with factory() as session:
        if existing_run_id is None:
            run_id = await _create_run_row(session, adapter.code)
        else:
            run_id = existing_run_id
        supplier_id = await _ensure_supplier_row(session, adapter.code)
        await session.commit()

        if component_ids is None:
            stmt = select(ComponentModel.id, ComponentModel.mpn).order_by(
                ComponentModel.created_at.asc()
            )
            result = await session.execute(stmt)
            targets: list[tuple[UUID, str]] = [
                (row.id, row.mpn) for row in result.all()
            ]
        else:
            stmt = select(ComponentModel.id, ComponentModel.mpn).where(
                ComponentModel.id.in_(component_ids)
            )
            result = await session.execute(stmt)
            targets = [(row.id, row.mpn) for row in result.all()]

    # Per-component loop. Open a fresh session per component so a failure
    # on one row doesn't poison the transaction for the next.
    for component_id, mpn in targets:
        processed += 1
        try:
            quote = await adapter.fetch_by_mpn(mpn)
        except SupplierError as exc:
            errors += 1
            async with factory() as session:
                await _record_error(
                    session,
                    run_id=run_id,
                    component_id=component_id,
                    supplier=adapter.code,
                    error=exc,
                )
                await session.commit()
            continue
        except Exception as exc:
            errors += 1
            _log.exception("supplier_sync.unknown_error supplier=%s mpn=%s", adapter.code, mpn)
            async with factory() as session:
                session.add(
                    SupplierSyncErrorModel(
                        id=uuid4(),
                        run_id=run_id,
                        component_id=component_id,
                        supplier=adapter.code,
                        error_code="UNKNOWN",
                        error_message=str(exc)[:2000],
                    )
                )
                await session.commit()
            continue

        if quote is None:
            continue

        async with factory() as session:
            wrote = await _upsert_prices_and_stock(
                session,
                component_id=component_id,
                supplier_id=supplier_id,
                quote=quote,
                today=today,
            )
            if wrote:
                component = await session.get(ComponentModel, component_id)
                if component is not None:
                    component.last_supplier_sync_at = datetime.now(UTC)
                updated += 1
            await session.commit()

    # Finalise run row.
    async with factory() as session:
        await _finalise_run(
            session,
            run_id=run_id,
            processed=processed,
            updated=updated,
            errors=errors,
        )

    return run_id


def _build_adapter_for(code: str) -> SupplierAdapter | None:
    """Build a single adapter from settings — used by `sync_one_supplier`
    so the Celery task can be enqueued by code without serialising adapter
    instances across the broker."""

    from app.infrastructure.suppliers.registry import enabled_adapters

    for adapter in enabled_adapters():
        if adapter.code == code:
            return adapter
    return None


@celery_app.task(name="supplier_sync.sync_one_supplier", bind=True, max_retries=3)  # type: ignore[untyped-decorator]
def sync_one_supplier(
    self: object,
    supplier_code: str,
    existing_run_id: str | None = None,
) -> str:
    """Celery task: sync one supplier across the whole catalogue.

    Returns the run_id as a string for traceability in Celery results.
    Raised typed errors are not re-tried here — each component failure
    is captured into `supplier_sync_errors` and the run finalises as
    `partial` instead.

    `existing_run_id` lets the HTTP trigger pre-create the `supplier_sync_runs`
    row so the operator gets the real ID back synchronously.
    """

    adapter = _build_adapter_for(supplier_code)
    if adapter is None:
        _log.warning(
            "supplier_sync.sync_one_supplier.skipped code=%s reason=not_enabled_or_no_creds",
            supplier_code,
        )
        return ""

    run_uuid = UUID(existing_run_id) if existing_run_id else None
    run_id = asyncio.run(_run_for_supplier_isolated(adapter, run_uuid))
    return str(run_id)


async def _run_for_supplier_isolated(
    adapter: SupplierAdapter, run_uuid: UUID | None
) -> UUID:
    """Run one supplier sync with a fresh DB engine bound to THIS loop.

    Celery prefork reuses worker processes across tasks, each on a new
    ``asyncio.run`` loop. `forget_engine()` abandons any engine left over
    from a previous (now closed) loop so the work below builds a fresh one
    on the current loop; `dispose_engine()` returns its connections before
    the loop closes. Without this the second task on a process fails with
    "got Future attached to a different loop" (see `db/session.py`).
    """

    forget_engine()
    try:
        return await _run_for_supplier(adapter, existing_run_id=run_uuid)
    finally:
        await dispose_engine()


@celery_app.task(name="supplier_sync.run_daily_sync")  # type: ignore[untyped-decorator]
def run_daily_sync() -> list[str]:
    """Beat-triggered orchestrator. Enqueues one `sync_one_supplier` task
    per enabled supplier so they run in parallel on the worker pool."""

    settings = get_settings()
    enqueued: list[str] = []
    for code in settings.supplier_sync_enabled_suppliers:
        task = sync_one_supplier.delay(code)
        enqueued.append(f"{code}:{task.id}")
    _log.info("supplier_sync.run_daily_sync.enqueued count=%d", len(enqueued))
    return enqueued
