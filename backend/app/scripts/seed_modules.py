"""Seed sample modules + DAG edges (Figma 46:5593).

Inserts:
- Módulo Sensor Ambiental (3 component children)
- Sistema Potencia BLDC (one nested sub-module + extra component children)
- Etapa Driver (sub-module, child of Sistema Potencia BLDC)

The seed reuses at least one component as a child of two different modules
(DAG case) — `STM32F407VGT6` ends up in both Sensor Ambiental and Sistema
Potencia BLDC.

Usage:
    python -m app.scripts.seed_modules [--reset]

`--reset` truncates `module_children` and `modules` first. Without it, the
script refuses to insert if `modules` is non-empty (exit 2).

Requires `seed_components` to have been run first — refuses with exit 3
when the referenced components are missing.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from dataclasses import dataclass
from datetime import date, timedelta
from uuid import UUID

from sqlalchemy import select, text

from app.application.services.modules_service import (
    AddChildInput,
    ModuleCreate,
    ModuleService,
)
from app.infrastructure.db.models.component import ComponentModel
from app.infrastructure.db.session import get_session_factory


@dataclass
class _SeedSpec:
    sku: str
    name: str
    description: str
    version: str
    fabricante: str
    location: str
    tipo_almacenamiento: str
    stock: int
    component_children_mpns: list[tuple[str, int]]  # (mpn, quantity)
    sub_module_children_skus: list[tuple[str, int]]  # (sku, quantity)


SEED_SPECS: list[_SeedSpec] = [
    _SeedSpec(
        sku="MOD-SENS-001",
        name="Módulo Sensor Ambiental",
        description="Conjunto completo de sensores ambientales con MCU",
        version="v1.2",
        fabricante="Custom Assembly",
        location="G-M-01",
        tipo_almacenamiento="Gaveta",
        stock=25,
        component_children_mpns=[
            ("STM32F407VGT6", 1),
            ("BME280", 1),
            ("GRM31CR71H106KA12L", 2),  # condensador cerámico
        ],
        sub_module_children_skus=[],
    ),
    _SeedSpec(
        sku="MOD-DRV-001",
        name="Etapa Driver",
        description="Transistores de potencia y drivers",
        version="v1.0",
        fabricante="Custom Assembly",
        location="G-M-06",
        tipo_almacenamiento="Almacén",
        stock=32,
        component_children_mpns=[
            ("IRF1404 - MOSFET N 100V 162A", 4),
            ("SS14", 4),
        ],
        sub_module_children_skus=[],
    ),
    _SeedSpec(
        sku="MOD-PWR-001",
        name="Sistema Potencia BLDC",
        description="Módulo de potencia completo para control de motor BLDC",
        version="v1.0",
        fabricante="Custom Assembly",
        location="G-M-05",
        tipo_almacenamiento="Almacén",
        stock=18,
        component_children_mpns=[
            ("STM32F407VGT6", 1),  # DAG: same MCU reused
            ("LM2596S-5.0", 1),
        ],
        sub_module_children_skus=[
            ("MOD-DRV-001", 1),  # nests Etapa Driver
        ],
    ),
]


async def _seed(reset: bool) -> int:
    """Returns 0 on success, 2 if refusing to re-seed, 3 if missing components."""
    session_factory = get_session_factory()
    async with session_factory() as session:
        # Check if modules already exist
        existing = (await session.execute(select(text("1")).select_from(text("modules")))).first()
        if existing is not None and not reset:
            print(
                "Refusing to seed: modules table already has rows. Pass --reset to start over.",
                file=sys.stderr,
            )
            return 2

        if reset:
            await session.execute(
                text("TRUNCATE module_children, modules RESTART IDENTITY CASCADE")
            )
            await session.commit()

        # Resolve components by mpn
        mpns_needed = sorted(
            {mpn for spec in SEED_SPECS for (mpn, _) in spec.component_children_mpns}
        )
        comp_rows = (
            await session.execute(
                select(ComponentModel.id, ComponentModel.mpn).where(
                    ComponentModel.mpn.in_(mpns_needed)
                )
            )
        ).all()
        comp_by_mpn: dict[str, UUID] = {row[1]: row[0] for row in comp_rows}

        missing = [mpn for mpn in mpns_needed if mpn not in comp_by_mpn]
        if missing:
            print(
                f"Missing components: {', '.join(missing)}. "
                "Run `python -m app.scripts.seed_components` first.",
                file=sys.stderr,
            )
            return 3

        svc = ModuleService(session)
        created_by_sku: dict[str, UUID] = {}

        # Order: create modules with no sub-module dependencies first.
        ordered_specs = sorted(SEED_SPECS, key=lambda s: len(s.sub_module_children_skus))

        for spec in ordered_specs:
            module = await svc.create(
                ModuleCreate(
                    sku=spec.sku,
                    name=spec.name,
                    description=spec.description,
                    version=spec.version,
                    fabricante=spec.fabricante,
                    location=spec.location,
                    tipo_almacenamiento=spec.tipo_almacenamiento,
                    stock=spec.stock,
                    fecha_creacion=date.today() - timedelta(days=30),
                )
            )
            created_by_sku[spec.sku] = module.id

            # Add component children
            for mpn, qty in spec.component_children_mpns:
                await svc.add_child(
                    module.id,
                    AddChildInput(child_component_id=comp_by_mpn[mpn], quantity=qty),
                )

            # Add sub-module children
            for sub_sku, qty in spec.sub_module_children_skus:
                sub_id = created_by_sku.get(sub_sku)
                if sub_id is None:
                    print(
                        f"Skipping sub-module {sub_sku} — not yet seeded.",
                        file=sys.stderr,
                    )
                    continue
                await svc.add_child(
                    module.id,
                    AddChildInput(child_module_id=sub_id, quantity=qty),
                )

        print(
            f"Seeded {len(created_by_sku)} modules with their DAG children "
            f"(component leaves + nested sub-modules)."
        )
        return 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reset", action="store_true", help="TRUNCATE first")
    args = parser.parse_args()
    sys.exit(asyncio.run(_seed(reset=args.reset)))


if __name__ == "__main__":
    main()
