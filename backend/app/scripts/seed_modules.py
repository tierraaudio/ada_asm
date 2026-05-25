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
import random
import sys
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select, text

from app.application.services.modules_service import (
    AddChildInput,
    ModuleCreate,
    ModuleService,
)
from app.domain.entities.stock_event import StockEvent
from app.infrastructure.db.models.component import ComponentModel
from app.infrastructure.db.session import get_session_factory
from app.infrastructure.repositories.stock_event_repository import (
    SqlAlchemyStockEventRepository,
)

# Holded-style customer pool used by `delivered` events. Real ID values match
# the format Holded exposes (prefix `cli_` + opaque suffix); names are
# fictional EU/LATAM industrial customers for synthetic richness.
_CUSTOMERS: list[tuple[str, str]] = [
    ("cli_AB12CD34", "Robotics Iberia SL"),
    ("cli_EF56GH78", "Aeronáutica del Norte SA"),
    ("cli_IJ90KL12", "Industria Vasca de Drones"),
    ("cli_MN34OP56", "Sensores Ambientales del Mediterráneo SL"),
    ("cli_QR78ST90", "AutoMotrix LATAM SAS"),
    ("cli_UV12WX34", "MeteoTech Asturias SL"),
]


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
    # --- Level 0 leaves (sub-sub-modules) — built first ---
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
        sku="MOD-REG-001",
        name="Regulador 5V",
        description="Subensamblado de regulación lineal 5V",
        version="v1.1",
        fabricante="Custom Assembly",
        location="G-M-07",
        tipo_almacenamiento="Gaveta",
        stock=40,
        component_children_mpns=[
            ("AMS1117-3.3", 2),
            ("GRM31CR71H106KA12L", 4),
        ],
        sub_module_children_skus=[],
    ),
    _SeedSpec(
        sku="MOD-FILT-001",
        name="Filtro EMI",
        description="Filtro EMI pasivo de 3 etapas",
        version="v1.0",
        fabricante="Custom Assembly",
        location="G-M-08",
        tipo_almacenamiento="Gaveta",
        stock=60,
        component_children_mpns=[
            ("RC0805FR-074K7", 6),
            ("RC0805JR-07330R", 4),
            ("GRM31CR71H106KA12L", 3),
        ],
        sub_module_children_skus=[],
    ),
    _SeedSpec(
        sku="MOD-COMM-001",
        name="Interfaz UART/USB",
        description="Subensamblado de comunicaciones serie",
        version="v2.0",
        fabricante="Custom Assembly",
        location="G-M-09",
        tipo_almacenamiento="Almacén",
        stock=22,
        component_children_mpns=[
            ("USB Type-C 24-pin Female SMD", 1),
            ("CL10A106KP8NNNC", 2),
        ],
        sub_module_children_skus=[],
    ),
    # --- Level 1 — module compositions including sub-modules ---
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
            ("GRM31CR71H106KA12L", 2),
        ],
        sub_module_children_skus=[],
    ),
    _SeedSpec(
        sku="MOD-IMU-001",
        name="Módulo IMU 6-DoF",
        description="Sensor inercial con MCU y comunicaciones",
        version="v1.0",
        fabricante="Custom Assembly",
        location="G-M-10",
        tipo_almacenamiento="Gaveta",
        stock=15,
        component_children_mpns=[
            ("STM32F407VGT6", 1),
            ("MPU-6050", 1),
        ],
        sub_module_children_skus=[
            ("MOD-COMM-001", 1),
        ],
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
            ("STM32F407VGT6", 1),  # DAG: same MCU reused across modules
            ("LM2596S-5.0", 1),
        ],
        sub_module_children_skus=[
            ("MOD-DRV-001", 1),  # nests Etapa Driver (depth 2)
            ("MOD-FILT-001", 1),  # nests Filtro EMI
        ],
    ),
    _SeedSpec(
        sku="MOD-DAQ-001",
        name="Módulo de Adquisición de Datos",
        description="Adquisición analógica con conversión + comunicaciones",
        version="v1.0",
        fabricante="Custom Assembly",
        location="G-M-11",
        tipo_almacenamiento="Almacén",
        stock=10,
        component_children_mpns=[
            ("ATMEGA328P-PU", 1),
            ("LM358", 2),
        ],
        sub_module_children_skus=[
            ("MOD-REG-001", 1),
            ("MOD-FILT-001", 1),
        ],
    ),
    # --- Level 2 — top-level systems composing the above (depth=3) ---
    _SeedSpec(
        sku="MOD-DRONE-001",
        name="Plataforma Dron Cuadricoptero",
        description=(
            "Sistema completo de control para dron cuadricoptero — "
            "incluye potencia + IMU + adquisición. Llega a profundidad 3 "
            "via Sistema Potencia BLDC → Etapa Driver."
        ),
        version="v0.9",
        fabricante="Custom Assembly",
        location="G-M-12",
        tipo_almacenamiento="Almacén",
        stock=4,
        component_children_mpns=[
            ("RPi-Pico-W", 1),
        ],
        sub_module_children_skus=[
            ("MOD-PWR-001", 4),  # 4 motores → 4 etapas de potencia
            ("MOD-IMU-001", 1),
            ("MOD-DAQ-001", 1),
        ],
    ),
    _SeedSpec(
        sku="MOD-STATION-001",
        name="Estación Meteorológica",
        description="Sistema autónomo con sensores + comunicaciones + alimentación regulada",
        version="v1.3",
        fabricante="Custom Assembly",
        location="G-M-13",
        tipo_almacenamiento="Almacén",
        stock=7,
        component_children_mpns=[
            ("ESP32-WROOM-32", 1),
            ("CR2032", 2),
        ],
        sub_module_children_skus=[
            ("MOD-SENS-001", 1),
            ("MOD-REG-001", 1),
            ("MOD-COMM-001", 1),
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
            # Plain DELETEs (not TRUNCATE ... CASCADE) so the component-level
            # stock_events keep their rows. A TRUNCATE on `modules` with
            # CASCADE would also empty the *entire* stock_events table via
            # the module_id FK chain.
            await session.execute(text("DELETE FROM stock_events WHERE module_id IS NOT NULL"))
            await session.execute(text("DELETE FROM module_children"))
            await session.execute(text("DELETE FROM modules"))
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

        # ----- Module-level stock_events (fabricated + delivered) -----
        rng = random.Random(20260525)
        stock_event_repo = SqlAlchemyStockEventRepository(session)
        total_events = 0
        today = date.today()
        for spec in ordered_specs:
            module_id = created_by_sku[spec.sku]
            # Fabricate 2-3 batches over the last ~6 months. Unit cost
            # approximates the recipe cost for that module (rough order of
            # magnitude); fluctuates ±10 % per batch.
            base_unit_cost = Decimal(rng.choice(["12.50", "28.75", "55.40", "84.90", "120.00"]))
            fabricated_batches = rng.randint(2, 3)
            fabricated_total = 0
            for i in range(fabricated_batches):
                qty = rng.randint(5, 25)
                fabricated_total += qty
                drift = Decimal(str(rng.uniform(0.9, 1.1))).quantize(Decimal("0.0001"))
                unit_cost = (base_unit_cost * drift).quantize(Decimal("0.0001"))
                total_cost = (unit_cost * qty).quantize(Decimal("0.0001"))
                occurred = today - timedelta(days=rng.randint(30, 180))
                await stock_event_repo.save(
                    StockEvent(
                        module_id=module_id,
                        kind="fabricated",
                        quantity=qty,
                        occurred_at=occurred,
                        unit_cost=unit_cost,
                        total_cost=total_cost,
                        currency="EUR",
                        notes=f"Lote fabricado #{i + 1}",
                    )
                )
                total_events += 1

            # Deliver 1-2 shipments to customers. Total delivered MUST be
            # strictly less than fabricated_total so the resulting stock
            # is positive and consistent with the spec's `stock`.
            max_delivered = max(0, fabricated_total - spec.stock)
            if max_delivered > 0:
                shipments = rng.randint(1, 2)
                remaining = max_delivered
                for i in range(shipments):
                    if remaining <= 0:
                        break
                    qty = rng.randint(1, max(1, remaining // (shipments - i)))
                    remaining -= qty
                    customer = rng.choice(_CUSTOMERS)
                    occurred = today - timedelta(days=rng.randint(5, 60))
                    await stock_event_repo.save(
                        StockEvent(
                            module_id=module_id,
                            kind="delivered",
                            quantity=qty,
                            occurred_at=occurred,
                            customer_id_holded=customer[0],
                            customer_name_snapshot=customer[1],
                            notes=f"Entrega #{i + 1}",
                        )
                    )
                    total_events += 1
        await session.commit()

        print(
            f"Seeded {len(created_by_sku)} modules with their DAG children "
            f"(component leaves + nested sub-modules) + {total_events} module-level "
            f"stock events (fabricated/delivered)."
        )
        return 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reset", action="store_true", help="TRUNCATE first")
    args = parser.parse_args()
    sys.exit(asyncio.run(_seed(reset=args.reset)))


if __name__ == "__main__":
    main()
