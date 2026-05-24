"""Seed ~10 sample components + suppliers + prices + stock + events.

Usage:
    python -m app.scripts.seed_components [--reset]

The seed mirrors the Figma copy (ACS712, BME280, ESP32-WROOM-32E, …) so the
list / detail / charts have realistic data on a fresh clone without needing
real supplier integrations.

`--reset` truncates `stock_events`, `supplier_stocks`, `supplier_prices`,
`suppliers` and `components` first. Without it, the script refuses to insert
if `components` is non-empty (exit 2).
"""

from __future__ import annotations

import argparse
import asyncio
import random
import sys
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import cast
from uuid import UUID

from sqlalchemy import text

from app.domain.entities.component import Component, NatoScoreValue, TierValue
from app.domain.entities.stock_event import StockEvent
from app.domain.entities.supplier import Supplier
from app.domain.entities.supplier_price import QtyTier, SupplierPrice
from app.domain.entities.supplier_stock import SupplierStock
from app.domain.repositories.component_repository import ComponentFilters
from app.infrastructure.db.session import get_session_factory
from app.infrastructure.repositories.component_repository import (
    SqlAlchemyComponentRepository,
)
from app.infrastructure.repositories.stock_event_repository import (
    SqlAlchemyStockEventRepository,
)
from app.infrastructure.repositories.supplier_price_repository import (
    SqlAlchemySupplierPriceRepository,
)
from app.infrastructure.repositories.supplier_repository import (
    SqlAlchemySupplierRepository,
)
from app.infrastructure.repositories.supplier_stock_repository import (
    SqlAlchemySupplierStockRepository,
)

SUPPLIER_NAMES = ["DigiKey", "Mouser", "Farnell", "RS", "TME"]


@dataclass
class ComponentSeed:
    mpn: str
    sku: str
    name: str
    family: str
    description: str
    location: str
    fabricante: str
    tipo_almacenamiento: str
    tier: TierValue
    nato_score: NatoScoreValue
    country_of_origin: str
    stock: int
    stock_min: int
    preferred_supplier: str
    datasheet_url: str
    verificado: bool


# Tier per family rule of thumb:
#   1 — Chips / Microcontroladores / Memorias (criticality very high)
#   2 — Sensores / Comunicaciones (high)
#   3 — Reguladores / Condensadores / Resistencias / Diodos (medium)
#   4 — Conectores / Plásticos / Placas (low)
SAMPLE_COMPONENTS: list[ComponentSeed] = [
    ComponentSeed(
        mpn="STM32F407VGT6",
        sku="MCU-001",
        name="STM32F407VGT6 - ARM Cortex-M4 MCU",
        family="Microcontroladores",
        description="MCU de 32 bits a 168 MHz, 1 MB flash, 192 KB SRAM.",
        location="G-A-12",
        fabricante="STMicroelectronics",
        tipo_almacenamiento="Gaveta",
        tier=1,
        nato_score="A+",
        country_of_origin="FR",
        stock=145,
        stock_min=5,
        preferred_supplier="DigiKey",
        datasheet_url="https://www.st.com/resource/en/datasheet/stm32f407vg.pdf",
        verificado=True,
    ),
    ComponentSeed(
        mpn="GRM31CR71H106KA12L",
        sku="CAP-047",
        name="Condensador cerámico 10µF 50V X7R 1206",
        family="Condensadores",
        description="MLCC X7R 1206, 10 µF, 50 V, ±10%.",
        location="G-C-08",
        fabricante="Murata",
        tipo_almacenamiento="Bobina",
        tier=3,
        nato_score="A",
        country_of_origin="JP",
        stock=850,
        stock_min=50,
        preferred_supplier="TME",
        datasheet_url="https://www.murata.com/datasheet/grm31cr71h106ka12.pdf",
        verificado=True,
    ),
    ComponentSeed(
        mpn="RC0805FR-0710K",
        sku="RES-112",
        name="Resistencia 10 kΩ 0805 1%",
        family="Resistencias",
        description="SMD 0805, 10 kΩ, ±1%, 1/8 W.",
        location="G-S-11",
        fabricante="Yageo",
        tipo_almacenamiento="Bobina",
        tier=3,
        nato_score="A+",
        country_of_origin="TW",
        stock=800,
        stock_min=80,
        preferred_supplier="TME",
        datasheet_url="https://www.yageo.com/upload/media/product/productsearch/datasheet/rchip/PYu-RC_Group_51_RoHS_L_11.pdf",
        verificado=True,
    ),
    ComponentSeed(
        mpn="BME280",
        sku="SEN-008",
        name="BME280 - Sensor ambiental digital",
        family="Sensores",
        description="Sensor de temperatura, humedad y presión barométrica I2C/SPI.",
        location="G-S-15",
        fabricante="Bosch Sensortec",
        tipo_almacenamiento="Gaveta",
        tier=2,
        nato_score="A",
        country_of_origin="DE",
        stock=68,
        stock_min=12,
        preferred_supplier="Mouser",
        datasheet_url="https://www.bosch-sensortec.com/media/boschsensortec/downloads/datasheets/bst-bme280-ds002.pdf",
        verificado=True,
    ),
    ComponentSeed(
        mpn="LM2596S-5.0",
        sku="REG-015",
        name="LM2596 - Regulador Buck 5V step-down",
        family="Fuentes de alimentación",
        description="Regulador DC-DC step-down, 5 V fija, 3 A.",
        location="G-P-06",
        fabricante="Texas Instruments",
        tipo_almacenamiento="Bandeja",
        tier=3,
        nato_score="A+",
        country_of_origin="US",
        stock=54,
        stock_min=15,
        preferred_supplier="TME",
        datasheet_url="https://www.ti.com/lit/ds/symlink/lm2596.pdf",
        verificado=True,
    ),
    ComponentSeed(
        mpn="ACS712ELCTR-20A-T",
        sku="SEN-024",
        name="ACS712 - Sensor corriente Hall ±20A",
        family="Sensores",
        description="Sensor de corriente Hall, salida lineal hasta ±20 A.",
        location="G-S-18",
        fabricante="Allegro MicroSystems",
        tipo_almacenamiento="Gaveta",
        tier=2,
        nato_score="A+",
        country_of_origin="US",
        stock=42,
        stock_min=10,
        preferred_supplier="DigiKey",
        datasheet_url="https://www.allegromicro.com/-/media/files/datasheets/acs712-datasheet.pdf",
        verificado=True,
    ),
    ComponentSeed(
        mpn="B340A",
        sku="DIO-095",
        name="B340A - Diodo Schottky 3A 40V",
        family="Diodos",
        description="Diodo Schottky de potencia, encapsulado SMA.",
        location="G-T-21",
        fabricante="Diodes Inc.",
        tipo_almacenamiento="Bobina",
        tier=3,
        nato_score="A",
        country_of_origin="TW",
        stock=120,
        stock_min=40,
        preferred_supplier="Farnell",
        datasheet_url="https://www.diodes.com/assets/Datasheets/B340A.pdf",
        verificado=True,
    ),
    ComponentSeed(
        mpn="IRF1404 - MOSFET N 100V 162A",
        sku="TRN-006",
        name="IRF1404 - MOSFET N 100V 162A",
        family="Transistores",
        description="MOSFET de potencia, encapsulado TO-220AB.",
        location="G-T-09",
        fabricante="Infineon",
        tipo_almacenamiento="Bandeja",
        tier=3,
        nato_score="A",
        country_of_origin="DE",
        stock=15,
        stock_min=10,
        preferred_supplier="Mouser",
        datasheet_url="https://www.infineon.com/dgdl/irf1404pbf.pdf",
        verificado=False,
    ),
    ComponentSeed(
        mpn="USB Type-C 24-pin Female SMD",
        sku="CON-076",
        name="USB Type-C 24-pin Female SMD",
        family="Conectores",
        description="Conector USB-C hembra, montaje superficial.",
        location="G-N-04",
        fabricante="Amphenol",
        tipo_almacenamiento="Bandeja",
        tier=4,
        nato_score="B",
        country_of_origin="CN",
        stock=0,
        stock_min=20,
        preferred_supplier="DigiKey",
        datasheet_url="https://www.amphenol-cs.com/media/wysiwyg/files/drawing/12401548.pdf",
        verificado=True,
    ),
    ComponentSeed(
        mpn="ESP32-WROOM-32",
        sku="MOD-053",
        name="ESP32-WROOM-32 - Módulo WiFi+BT",
        family="Módulos",
        description="Módulo SoC ESP32 con WiFi y Bluetooth integrados.",
        location="G-M-02",
        fabricante="Espressif",
        tipo_almacenamiento="Gaveta",
        tier=1,
        nato_score="D",
        country_of_origin="CN",
        stock=0,
        stock_min=8,
        preferred_supplier="TME",
        datasheet_url="https://www.espressif.com/sites/default/files/documentation/esp32-wroom-32_datasheet_en.pdf",
        verificado=True,
    ),
    ComponentSeed(
        mpn="NE555",
        sku="IC-125",
        name="NE555 - Timer SOIC-8",
        family="Microcontroladores",
        description="Temporizador clásico NE555 en SOIC-8.",
        location="G-A-22",
        fabricante="Texas Instruments",
        tipo_almacenamiento="Bobina",
        tier=1,
        nato_score="A+",
        country_of_origin="US",
        stock=0,
        stock_min=10,
        preferred_supplier="TME",
        datasheet_url="https://www.ti.com/lit/ds/symlink/ne555.pdf",
        verificado=True,
    ),
]


def _qty_tier_price(base_unit_cost: Decimal, qty_tier: QtyTier) -> Decimal:
    """Stepped discount: bigger qty_tier → lower per-unit price."""
    discount = {
        1: Decimal("1.00"),
        10: Decimal("0.85"),
        100: Decimal("0.72"),
        1000: Decimal("0.61"),
    }
    return (base_unit_cost * discount[qty_tier]).quantize(Decimal("0.0001"))


async def _seed(reset: bool) -> int:
    random.seed(42)  # deterministic
    factory = get_session_factory()
    async with factory() as session:
        components_repo = SqlAlchemyComponentRepository(session)
        suppliers_repo = SqlAlchemySupplierRepository(session)
        prices_repo = SqlAlchemySupplierPriceRepository(session)
        stocks_repo = SqlAlchemySupplierStockRepository(session)
        events_repo = SqlAlchemyStockEventRepository(session)

        if reset:
            await session.execute(
                text(
                    "TRUNCATE stock_events, supplier_stocks, supplier_prices, "
                    "suppliers, components RESTART IDENTITY CASCADE"
                )
            )
            await session.commit()
        else:
            existing = await components_repo.list(filters=ComponentFilters(), page=1, page_size=1)
            if existing.total > 0:
                print(
                    f"Refusing to seed: {existing.total} components already exist. "
                    "Pass --reset to truncate and re-seed.",
                    file=sys.stderr,
                )
                return 2

        # Suppliers first — needed for proveedor_preferente FK.
        supplier_by_name: dict[str, UUID] = {}
        for name in SUPPLIER_NAMES:
            saved = await suppliers_repo.save(Supplier(name=name))
            supplier_by_name[name] = saved.id

        today = date.today()
        for sample in SAMPLE_COMPONENTS:
            component = await components_repo.save(
                Component(
                    mpn=sample.mpn,
                    sku=sample.sku,
                    name=sample.name,
                    family=sample.family,
                    description=sample.description,
                    datasheet_url=sample.datasheet_url,
                    location=sample.location,
                    fabricante=sample.fabricante,
                    tipo_almacenamiento=sample.tipo_almacenamiento,
                    holded_id=f"HLD-{sample.sku}",
                    fecha_creacion=today - timedelta(days=random.randint(180, 720)),
                    verificado=sample.verificado,
                    notas=None,
                    stock=sample.stock,
                    stock_min=sample.stock_min,
                    tier=sample.tier,
                    nato_score=sample.nato_score,
                    country_of_origin=sample.country_of_origin,
                    proveedor_preferente_id=supplier_by_name[sample.preferred_supplier],
                )
            )

            # Supplier prices: today's snapshot for every supplier x every qty_tier.
            base_unit_cost_by_supplier = {
                supplier: Decimal(str(round(random.uniform(0.50, 12.00), 2)))
                for supplier in SUPPLIER_NAMES
            }
            for supplier_name in SUPPLIER_NAMES:
                base = base_unit_cost_by_supplier[supplier_name]
                for qty_tier in cast(list[QtyTier], [1, 10, 100, 1000]):
                    await prices_repo.save(
                        SupplierPrice(
                            component_id=component.id,
                            supplier_id=supplier_by_name[supplier_name],
                            qty_tier=qty_tier,
                            price=_qty_tier_price(base, qty_tier),
                            valid_from=today,
                        )
                    )

            # Supplier stock snapshots: one per supplier as of today.
            # When the component itself has 0 stock, vary supplier stock so the
            # FE can show "rojo (sin nada en proveedores)" vs "ámbar (proveedor
            # tiene)" reliably.
            local_out = sample.stock == 0
            for supplier_name in SUPPLIER_NAMES:
                if local_out and supplier_name in {"Farnell", "RS"}:
                    quantity = 0
                else:
                    quantity = random.randint(0, 320) if local_out else random.randint(50, 320)
                await stocks_repo.save(
                    SupplierStock(
                        component_id=component.id,
                        supplier_id=supplier_by_name[supplier_name],
                        quantity=quantity,
                        snapshot_at=today,
                    )
                )

            # Stock events — mix of purchases and consumptions over the last
            # ~6 months. Helps the future Historial view.
            for _ in range(random.randint(3, 5)):
                days_ago = random.randint(10, 180)
                occurred = today - timedelta(days=days_ago)
                if random.random() < 0.65:
                    supplier_name = random.choice(SUPPLIER_NAMES)
                    unit_cost = base_unit_cost_by_supplier[supplier_name]
                    qty = random.choice([10, 25, 50, 100, 250])
                    total = (unit_cost * Decimal(qty)).quantize(Decimal("0.0001"))
                    await events_repo.save(
                        StockEvent(
                            component_id=component.id,
                            kind="purchase",
                            quantity=qty,
                            occurred_at=occurred,
                            supplier_id=supplier_by_name[supplier_name],
                            unit_cost=unit_cost,
                            total_cost=total,
                            currency="EUR",
                        )
                    )
                else:
                    project_name = random.choice(
                        [
                            "Sistema Domótica Retrofit",
                            "Maqueta TerraMix",
                            "Banco pruebas Reflex",
                            "Adaptador BLE→RS485",
                        ]
                    )
                    await events_repo.save(
                        StockEvent(
                            component_id=component.id,
                            kind="consumption",
                            quantity=random.choice([1, 2, 5, 10, 15]),
                            occurred_at=occurred,
                            project_name_snapshot=project_name,
                        )
                    )

        await session.commit()
        print(
            f"Seeded {len(SAMPLE_COMPONENTS)} components, "
            f"{len(SUPPLIER_NAMES)} suppliers, prices, stocks and stock events."
        )
        return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Seed sample components into a fresh DB.")
    parser.add_argument("--reset", action="store_true", help="Truncate first, then re-seed.")
    args = parser.parse_args(argv)
    return asyncio.run(_seed(reset=args.reset))


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
