"""Migrate components from the legacy ASM inventory (taasm.stock_items).

Runs INSIDE the backend environment (direct DB + ingestion-service access),
typically via `az containerapp exec ... -- python -m app.scripts.migrate_asm`
or a one-off Container App Job. Resumable and batched so it can be run in
blocks across days (supplier API quotas).

Per item (a `stock_items` row exported to Blob as JSON):
  1. Skip if already migrated (a component with this legacy_asm_id exists).
  2. Try the normal ingestion (walks suppliers → family, datasheet, prices,
     per-supplier stock, the initial snapshot), seeding the ASM truth as
     manual overrides (ubicacion=locator, stock_inicial=amount, holded_id).
  3. If no supplier recognises the MPN, lift-and-shift a bare component from
     the ASM data (family left for review).
  4. Either way, stamp the legacy traceability columns.

Source data: Blob `legacy-asm-backup/asm_items.json` (array of objects with
keys: legacy_id, pn, mpn, name, description, locator, amount, holded_id,
cost, manufacturer, web, amount_per_tube).

Block selection: `--offset` / `--limit`. `--dry-run` plans without writing.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select, update

from app.application.services.component_ingestion_service import ComponentIngestionService
from app.core.config import get_settings
from app.core.exceptions import (
    ComponentMpnAlreadyRegisteredError,
    ComponentMpnNotFoundError,
    SupplierLookupUnavailableError,
)
from app.infrastructure.datasheet_storage import get_datasheet_storage
from app.infrastructure.db.models.component import ComponentModel
from app.infrastructure.db.session import get_session_factory

logging.basicConfig(level=logging.INFO, format="%(message)s")
_log = logging.getLogger("migrate_asm")

_SOURCE = "asm-legacy"
_BACKUP_CONTAINER = "legacy-asm-backup"
_ITEMS_BLOB = "asm_items.json"


async def _load_items() -> list[dict[str, Any]]:
    """Download the exported stock_items JSON from Blob (managed identity)."""

    from azure.identity.aio import DefaultAzureCredential
    from azure.storage.blob.aio import BlobClient

    settings = get_settings()
    account_url = settings.datasheet_storage_account_url
    if not account_url:
        raise RuntimeError("datasheet_storage_account_url unset; cannot read backup blob")
    credential = DefaultAzureCredential()
    blob = BlobClient(
        account_url,
        container_name=_BACKUP_CONTAINER,
        blob_name=_ITEMS_BLOB,
        credential=credential,
    )
    async with blob:
        stream = await blob.download_blob()
        raw = await stream.readall()
    await credential.close()
    items: list[dict[str, Any]] = json.loads(raw)
    return items


def _opt_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        n = round(float(value))
    except (TypeError, ValueError):
        return None
    return n if n > 0 else None


def _opt_decimal(value: Any) -> Decimal | None:
    if value in (None, "", 0):
        return None
    try:
        return Decimal(str(value))
    except (TypeError, ValueError):
        return None


async def _already_migrated(session: Any, legacy_id: str, mpn: str) -> bool:
    stmt = select(ComponentModel.id).where(
        (ComponentModel.legacy_asm_id == legacy_id) | (ComponentModel.mpn == mpn)
    )
    return (await session.execute(stmt)).first() is not None


def _legacy_values(item: dict[str, Any], now: datetime) -> dict[str, Any]:
    return {
        "legacy_asm_id": item.get("legacy_id"),
        "legacy_pn": item.get("pn") or None,
        "migration_source": _SOURCE,
        "migrated_at": now,
        "cost": _opt_decimal(item.get("cost")),
    }


async def _lift_shift(session: Any, item: dict[str, Any], now: datetime) -> None:
    """Create a bare component from ASM data when no supplier recognises it.

    NOT NULL columns (family, tier, nato_score, stock) get neutral defaults;
    family is left empty + needs_review (NATO/tier stay manual)."""

    model = ComponentModel(
        mpn=item["mpn"],
        sku=None,
        name=item.get("name") or item["mpn"],
        family="",
        description=item.get("description") or None,
        fabricante=item.get("manufacturer") or None,
        location=item.get("locator") or None,
        holded_id=item.get("holded_id") or None,
        stock=_opt_int(item.get("amount")) or 0,
        order_multiple=_opt_int(item.get("amount_per_tube")),
        tier=3,
        nato_score="C",
        family_needs_review=True,
        fecha_creacion=now.date(),
        **_legacy_values(item, now),
    )
    session.add(model)
    await session.commit()


async def _process(item: dict[str, Any], *, dry_run: bool) -> str:
    mpn = (item.get("mpn") or "").strip()
    if not mpn:
        return "skipped_no_mpn"

    factory = get_session_factory()
    now = datetime.now(UTC)
    async with factory() as session:
        if await _already_migrated(session, item.get("legacy_id", ""), mpn):
            return "skipped_done"
        if dry_run:
            return "would_process"

        service = ComponentIngestionService(session, storage=get_datasheet_storage())
        try:
            component, _ = await service.ingest(
                mpn,
                ubicacion=item.get("locator") or None,
                stock_inicial=_opt_int(item.get("amount")),
                holded_id=item.get("holded_id") or None,
            )
            await session.execute(
                update(ComponentModel)
                .where(ComponentModel.id == component.id)
                .values(**_legacy_values(item, now))
            )
            await session.commit()
            return "ingested"
        except ComponentMpnAlreadyRegisteredError:
            return "skipped_exists"
        except (ComponentMpnNotFoundError, SupplierLookupUnavailableError):
            await session.rollback()
            await _lift_shift(session, item, now)
            return "lifted"


async def _run(args: argparse.Namespace) -> int:
    items = await _load_items()
    items = [i for i in items if (i.get("mpn") or "").strip()]  # need an MPN
    window = items[args.offset : args.offset + args.limit] if args.limit else items[args.offset :]
    _log.info(
        "migrate_asm: %d items with MPN; window offset=%d limit=%s -> %d to process%s",
        len(items),
        args.offset,
        args.limit,
        len(window),
        " (DRY RUN)" if args.dry_run else "",
    )

    counts: dict[str, int] = {}
    for n, item in enumerate(window, 1):
        try:
            outcome = await _process(item, dry_run=args.dry_run)
        except Exception:
            _log.exception("migrate_asm: error on pn=%s mpn=%s", item.get("pn"), item.get("mpn"))
            outcome = "error"
        counts[outcome] = counts.get(outcome, 0) + 1
        _log.info(
            "[%d/%d] %s  pn=%s mpn=%s", n, len(window), outcome, item.get("pn"), item.get("mpn")
        )

    _log.info("migrate_asm: DONE %s", json.dumps(counts, sort_keys=True))
    return 0


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Migrate components from legacy ASM stock_items.")
    p.add_argument("--offset", type=int, default=0, help="Start index into the MPN item list.")
    p.add_argument("--limit", type=int, default=0, help="Max items to process (0 = all).")
    p.add_argument("--dry-run", action="store_true", help="Plan without writing.")
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    return asyncio.run(_run(args))


if __name__ == "__main__":
    raise SystemExit(main())
