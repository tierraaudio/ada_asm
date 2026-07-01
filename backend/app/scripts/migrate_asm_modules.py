"""Migrate ASM assemblies -> ada modules, then rebuild the BOM edges.

Strategy (option A): every assembly (a stock_item that is a PARENT in the ASM
`stock_edges` graph) becomes an ada module — finished products included; ada
projects stay for real customer work. Leaves remain components. The old BOM
graph is rebuilt as `module_children`.

Modes (ASM_MODE):
  modules_create  create a module per assembly (from asm_items.json), mark
                  OBSOLETO ones, and delete the component row that was migrated
                  for the same legacy item (it is a module now, not a part).
  bom_rebuild     resolve every stock_edge to ada entities (module/component)
                  via legacy_asm_id and bulk-insert module_children.

Both idempotent + resumable. Source data in Blob: asm_items.json + asm_edges.json.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import delete, insert, select

from app.infrastructure.db.models.component import ComponentModel
from app.infrastructure.db.models.module import ModuleModel
from app.infrastructure.db.models.module_child import ModuleChildModel
from app.infrastructure.db.session import get_session_factory
from app.scripts.migrate_asm import _load_items

_log = logging.getLogger("migrate_asm_modules")

_SOURCE = "asm-legacy"
_BACKUP_CONTAINER = "legacy-asm-backup"
_EDGES_BLOB = "asm_edges.json"

# ada `modules.family` is a fixed 4-value taxonomy (CHECK constraint):
# Board / Device / Bundle / Case. Map the ASM assembly pn prefix onto it.
_MODULE_FAMILY = {
    "TA-DEV": "Device",
    "TA-BMB": "Device",
    "TA-NEW": "Device",
    "TA-EUR": "Device",
    "TA-BRM": "Device",
    "TA-MOD": "Board",
    "TA-WIR": "Board",
    "RM-PCB": "Board",
    "PCB": "Board",
    "TA-FLV": "Bundle",
    "TA-PKG": "Bundle",
    "TA-BAS": "Bundle",
    "TA-DIY": "Bundle",
    "RM-CHA": "Case",
    "TA-COV": "Case",
    "TA-FRO": "Case",
    "RM-FIN": "Case",
    "RM-MON": "Case",
}
_MODULE_PFX_RE = re.compile(r"^(RM-[A-Z]+|TA-[A-Z]+|ST-[A-Z]+|PCB)")


def _module_family(pn: str) -> str:
    match = _MODULE_PFX_RE.match(pn.strip().upper())
    if match:
        return _MODULE_FAMILY.get(match.group(1), "Board")
    return "Board"


async def _load_edges() -> list[dict[str, Any]]:
    from azure.identity.aio import DefaultAzureCredential
    from azure.storage.blob.aio import BlobClient

    from app.core.config import get_settings

    account_url = get_settings().datasheet_storage_account_url
    if not account_url:
        raise RuntimeError("datasheet_storage_account_url unset; cannot read edges blob")
    credential = DefaultAzureCredential()
    blob = BlobClient(
        account_url,
        container_name=_BACKUP_CONTAINER,
        blob_name=_EDGES_BLOB,
        credential=credential,
    )
    async with blob:
        stream = await blob.download_blob()
        raw = await stream.readall()
    await credential.close()
    edges: list[dict[str, Any]] = json.loads(raw)
    return edges


def _qty(amount: Any) -> int:
    try:
        n = round(float(amount))
    except (TypeError, ValueError):
        return 1
    return max(1, min(32767, n))


def _stock(amount: Any) -> int:
    try:
        return max(0, round(float(amount)))
    except (TypeError, ValueError):
        return 0


async def _create_modules() -> int:
    items = {i["legacy_id"]: i for i in await _load_items()}
    edges = await _load_edges()
    assembly_ids = {e["src"] for e in edges}
    now = datetime.now(UTC)

    factory = get_session_factory()
    created = 0
    obsolete = 0
    missing = 0
    async with factory() as session:
        existing = set(
            (
                await session.execute(
                    select(ModuleModel.legacy_asm_id).where(ModuleModel.legacy_asm_id.is_not(None))
                )
            )
            .scalars()
            .all()
        )
        rows: list[dict[str, Any]] = []
        for aid in assembly_ids:
            if aid in existing:
                continue
            item = items.get(aid)
            if not item:
                missing += 1
                continue
            name = item.get("name") or item["pn"]
            is_obsolete = "OBSOLETO" in name.upper()
            obsolete += int(is_obsolete)
            rows.append(
                {
                    "sku": item["pn"],
                    "name": name[:200],
                    "description": item.get("description") or None,
                    "family": _module_family(item["pn"]),
                    "fabricante": (item.get("manufacturer") or None),
                    "location": item.get("locator") or None,
                    "stock": _stock(item.get("amount")),
                    "fecha_creacion": now.date(),
                    "legacy_asm_id": aid,
                    "legacy_pn": item["pn"],
                    "migration_source": _SOURCE,
                    "migrated_at": now,
                    "obsolete": is_obsolete,
                }
            )
            created += 1
        if rows:
            await session.execute(insert(ModuleModel), rows)
        # The same legacy items were migrated as components; they are modules now.
        await session.execute(
            delete(ComponentModel).where(ComponentModel.legacy_asm_id.in_(assembly_ids))
        )
        await session.commit()

    _log.info(
        "modules_create: assemblies=%d created=%d obsolete=%d missing_item=%d",
        len(assembly_ids),
        created,
        obsolete,
        missing,
    )
    return 0


async def _rebuild_bom() -> int:
    edges = await _load_edges()
    factory = get_session_factory()
    async with factory() as session:
        module_rows = (
            await session.execute(
                select(ModuleModel.legacy_asm_id, ModuleModel.id).where(
                    ModuleModel.legacy_asm_id.is_not(None)
                )
            )
        ).all()
        component_rows = (
            await session.execute(
                select(ComponentModel.legacy_asm_id, ComponentModel.id).where(
                    ComponentModel.legacy_asm_id.is_not(None)
                )
            )
        ).all()
        modules: dict[str, UUID] = {r.legacy_asm_id: r.id for r in module_rows}
        components: dict[str, UUID] = {r.legacy_asm_id: r.id for r in component_rows}

        seen: set[tuple[UUID, UUID | None, UUID | None]] = set()
        rows: list[dict[str, Any]] = []
        skip_parent = skip_child = self_ref = 0
        for edge in edges:
            parent = modules.get(edge["src"])
            if parent is None:
                skip_parent += 1
                continue
            child_module = modules.get(edge["dst"])
            child_component = None if child_module is not None else components.get(edge["dst"])
            if child_module is None and child_component is None:
                skip_child += 1
                continue
            if child_module == parent:
                self_ref += 1
                continue
            key = (parent, child_module, child_component)
            if key in seen:
                continue
            seen.add(key)
            rows.append(
                {
                    "parent_module_id": parent,
                    "child_module_id": child_module,
                    "child_component_id": child_component,
                    "quantity": _qty(edge["amount"]),
                    "sort_order": int(edge.get("ord") or 0),
                }
            )

        # Idempotent: clear previously-migrated edges before re-inserting.
        await session.execute(
            delete(ModuleChildModel).where(
                ModuleChildModel.parent_module_id.in_(
                    select(ModuleModel.id).where(ModuleModel.migration_source == _SOURCE)
                )
            )
        )
        if rows:
            await session.execute(insert(ModuleChildModel), rows)
        await session.commit()

    _log.info(
        "bom_rebuild: edges=%d inserted=%d skip_parent=%d skip_child=%d self_ref=%d",
        len(edges),
        len(rows),
        skip_parent,
        skip_child,
        self_ref,
    )
    return 0
