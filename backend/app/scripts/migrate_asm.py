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
import re
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select, update

from app.application.services.component_ingestion_service import ComponentIngestionService
from app.core.config import get_settings
from app.core.exceptions import (
    ComponentMpnAlreadyRegisteredError,
    ComponentMpnNotFoundError,
    SupplierRateLimitedError,
)
from app.infrastructure.datasheet_storage import get_datasheet_storage
from app.infrastructure.db.models.component import ComponentModel
from app.infrastructure.db.session import get_session_factory

logging.basicConfig(level=logging.INFO, format="%(message)s")
_log = logging.getLogger("migrate_asm")

_SOURCE = "asm-legacy"
_BACKUP_CONTAINER = "legacy-asm-backup"
_ITEMS_BLOB = "asm_items.json"

# MPNs that are internal codes (PCBs, sub-assemblies, modules) or Aliexpress
# never resolve at a distributor — lift-and-shift them directly instead of
# burning a ~45s supplier round-trip (and quota) on a guaranteed 404.
_INTERNAL_PREFIXES = ("PCB", "RM-", "TA-", "ASM-")


def _is_distributor(item: dict[str, Any]) -> bool:
    mpn = (item.get("mpn") or "").strip().upper()
    manufacturer = (item.get("manufacturer") or "").lower()
    return bool(mpn) and not mpn.startswith(_INTERNAL_PREFIXES) and "aliexpress" not in manufacturer


# --- Family reclassification from the ASM internal part number -----------------
# The legacy ASM `pn` deterministically encodes the component type (segment 4 of
# RM-COM-{SMD,THL}-XXX) or the category (RM-CON, TA-MOD, ...). This classifies
# every component (including lift-shifted ones with no supplier category), far
# more completely than supplier-category inference. See reclassify().
_COM_TYPE_FAMILY = {
    "RES": "Resistencias",
    "CAP": "Condensadores",
    "IC": "Circuitos Integrados",
    "POT": "Potenciómetros",
    "LED": "LEDs",
    "TRA": "Transistores",
    "REG": "Reguladores",
    "SWT": "Interruptores",
    "DIO": "Diodos",
    "REC": "Diodos",
    "IND": "Inductores",
    "REL": "Relés",
    "HEA": "Disipadores",
    "PSU": "Fuentes de alimentación",
    "VUM": "Instrumentación",
}
_CAT_FAMILY = {
    "RM-CON": "Conectores",
    "RM-HDW": "Hardware",
    "PCB": "PCB",
    "RM-PCB": "PCB",
    "STENCIL": "PCB",
    "RM-CHA": "Mecánica",
    "RM-FIN": "Mecánica",
    "RM-MON": "Mecánica",
    "RM-ALU": "Mecánica",
    "RM-MES": "Mecánica",
    "RM-SPR": "Mecánica",
    "RM-MAG": "Mecánica",
    "TA-COV": "Mecánica",
    "RM-PKG": "Embalaje",
    "RM-TRF": "Transformadores",
    "RM-WIR": "Cableado",
    "TA-WIR": "Cableado",
    "RM-BAT": "Baterías",
    "RM-MIC": "Micrófonos",
    "RM-DIS": "Displays",
    "RM-COM": "Fusibles",
    "TA-MOD": "Módulos",
    "TA-DEV": "Módulos",
    "TA-FLV": "Módulos",
    "TA-BMB": "Módulos",
    "TA-NEW": "Módulos",
    "TA-BAS": "Módulos",
    "TA-BRM": "Módulos",
    "TA-DIY": "Módulos",
    "TA-EUR": "Módulos",
}
_COM_RE = re.compile(r"^RM-COM-(?:SMD|THL)-([A-Z]+)")
_CAT_RE = re.compile(r"^(RM-[A-Z]+|TA-[A-Z]+|PCB|STENCIL)")


def _family_from_pn(pn: str | None) -> str | None:
    if not pn:
        return None
    p = pn.strip().upper()
    com = _COM_RE.match(p)
    if com:
        return _COM_TYPE_FAMILY.get(com.group(1))
    cat = _CAT_RE.match(p)
    if cat:
        return _CAT_FAMILY.get(cat.group(1))
    return None


async def _reclassify() -> int:
    """Assign a family (from legacy_pn) to every component still in review /
    without one. Deterministic, no supplier calls. Leaves correctly-classified
    components untouched."""

    factory = get_session_factory()
    counts: dict[str, int] = {}
    updated = 0
    unmatched = 0
    async with factory() as session:
        rows = (
            await session.execute(
                select(ComponentModel.id, ComponentModel.legacy_pn).where(
                    (ComponentModel.family == "") | (ComponentModel.family_needs_review.is_(True))
                )
            )
        ).all()
        for cid, pn in rows:
            family = _family_from_pn(pn)
            if not family:
                unmatched += 1
                continue
            await session.execute(
                update(ComponentModel)
                .where(ComponentModel.id == cid)
                .values(family=family, family_needs_review=False)
            )
            counts[family] = counts.get(family, 0) + 1
            updated += 1
        await session.commit()
    _log.info(
        "reclassify: candidates=%d updated=%d unmatched=%d by_family=%s",
        len(rows),
        updated,
        unmatched,
        json.dumps(counts, ensure_ascii=False, sort_keys=True),
    )
    return 0


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


class _QuotaExhausted(Exception):
    """A supplier returned 429 — daily quota is spent; stop the run so it can
    resume tomorrow (already-migrated items are skipped on the next pass)."""


async def _process(item: dict[str, Any], *, dry_run: bool, retries: int = 3) -> str:
    mpn = (item.get("mpn") or "").strip()
    if not mpn:
        return "skipped_no_mpn"

    factory = get_session_factory()
    async with factory() as session:
        if await _already_migrated(session, item.get("legacy_id", ""), mpn):
            return "skipped_done"
    if dry_run:
        return "would_distribute" if _is_distributor(item) else "would_lift"

    now = datetime.now(UTC)

    # Internal/PCB/Aliexpress → lift-and-shift directly (no supplier call).
    if not _is_distributor(item):
        async with factory() as session:
            await _lift_shift(session, item, now)
        return "lifted_internal"

    last_err: Exception | None = None
    for attempt in range(1, retries + 1):
        async with factory() as session:
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
            except ComponentMpnNotFoundError:
                # Suppliers responded but none recognised it → lift-and-shift.
                await session.rollback()
                await _lift_shift(session, item, now)
                return "lifted"
            except SupplierRateLimitedError as exc:
                raise _QuotaExhausted(str(exc)) from exc
            except Exception as exc:
                await session.rollback()
                last_err = exc
                if attempt < retries:
                    await asyncio.sleep(2 * attempt)

    _log.warning("migrate_asm: giving up after %d attempts mpn=%s: %s", retries, mpn, last_err)
    return "error"


async def _run(args: argparse.Namespace) -> int:
    items = await _load_items()
    items = [i for i in items if (i.get("mpn") or "").strip()]  # need an MPN
    if args.only == "distributor":
        items = [i for i in items if _is_distributor(i)]
    elif args.only == "internal":
        items = [i for i in items if not _is_distributor(i)]
    window = items[args.offset : args.offset + args.limit] if args.limit else items[args.offset :]
    _log.info(
        "migrate_asm: %d items (only=%s); window offset=%d limit=%s -> %d to process%s",
        len(items),
        args.only,
        args.offset,
        args.limit,
        len(window),
        " (DRY RUN)" if args.dry_run else "",
    )

    counts: dict[str, int] = {}
    for n, item in enumerate(window, 1):
        try:
            outcome = await _process(item, dry_run=args.dry_run)
        except _QuotaExhausted as exc:
            _log.warning("migrate_asm: QUOTA EXHAUSTED, stopping (resume later): %s", exc)
            break
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
    p.add_argument(
        "--only",
        choices=["all", "distributor", "internal"],
        default="all",
        help="Process only distributor (real MPN, gets enriched) or internal "
        "(PCB/assembly/Aliexpress, lift-shifted) items. Default all.",
    )
    p.add_argument("--dry-run", action="store_true", help="Plan without writing.")
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    return asyncio.run(_run(args))


if __name__ == "__main__":
    raise SystemExit(main())
