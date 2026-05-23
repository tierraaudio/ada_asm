"""Seed ~10 sample components + per-component purchase history.

Usage:
    python -m app.scripts.seed_components [--reset]

The seed mirrors the Figma copy (ACS712, BME280, ESP32-WROOM-32E, …) so the
list / detail / charts have realistic data on a fresh clone without needing
real supplier integrations. Each component receives 3-6 purchase rows spread
across the last 12 months.

TODO when Módulo lands: extend `--reset` to truncate module-component links
first, so the cascade is safe once we have FKs into `components`.
"""

from __future__ import annotations

import argparse
import asyncio
import random
import sys
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import text

from app.domain.entities.component import Component
from app.domain.entities.component_purchase import ComponentPurchase
from app.domain.repositories.component_repository import ComponentFilters
from app.infrastructure.db.session import get_session_factory
from app.infrastructure.repositories.component_purchase_repository import (
    SqlAlchemyComponentPurchaseRepository,
)
from app.infrastructure.repositories.component_repository import (
    SqlAlchemyComponentRepository,
)


SAMPLE_COMPONENTS: list[dict[str, Any]] = [
    {
        "mpn": "ACS712",
        "sku": "ACS712-30A",
        "name": "Sensor corriente Hall ±30A",
        "family": "Sensores",
        "description": "Sensor de corriente Hall de hasta ±30A, salida lineal.",
        "datasheet_url": "https://www.allegromicro.com/-/media/files/datasheets/acs712-datasheet.pdf",
        "location": "A-12-3",
        "supplier": "DigiKey",
        "price_per_100": Decimal("8.4500"),
        "stock": 145,
        "tier": "B",
        "nato_score": "otan",
        "country_of_origin": "US",
    },
    {
        "mpn": "B340A",
        "sku": "B340A-DIODE",
        "name": "Diodo Schottky 3A 40V",
        "family": "Diodos",
        "description": "Diodo Schottky de potencia, encapsulado SMA.",
        "datasheet_url": "https://www.diodes.com/assets/Datasheets/B340A.pdf",
        "location": "B-04-1",
        "supplier": "Farnell",
        "price_per_100": Decimal("0.2200"),
        "stock": 850,
        "tier": "D",
        "nato_score": "100_otan",
        "country_of_origin": "DE",
    },
    {
        "mpn": "BME280",
        "sku": "BME280-ENV",
        "name": "Sensor ambiental T/H/P",
        "family": "Sensores",
        "description": "Sensor de temperatura, humedad y presión barométrica.",
        "datasheet_url": "https://www.bosch-sensortec.com/media/boschsensortec/downloads/datasheets/bst-bme280-ds002.pdf",
        "location": "A-08-2",
        "supplier": "DigiKey",
        "price_per_100": Decimal("4.7800"),
        "stock": 320,
        "tier": "B",
        "nato_score": "allied_otan",
        "country_of_origin": "JP",
    },
    {
        "mpn": "ESP32-WROOM-32E",
        "sku": "ESP32-E",
        "name": "Módulo WiFi + Bluetooth",
        "family": "Microcontroladores",
        "description": "Módulo SoC con WiFi y Bluetooth de Espressif.",
        "datasheet_url": "https://www.espressif.com/sites/default/files/documentation/esp32-wroom-32e_esp32-wroom-32ue_datasheet_en.pdf",
        "location": "C-01-1",
        "supplier": "Mouser",
        "price_per_100": Decimal("3.5500"),
        "stock": 280,
        "tier": "A",
        "nato_score": "high_risk",
        "country_of_origin": "CN",
    },
    {
        "mpn": "LM2596",
        "sku": "LM2596-ADJ",
        "name": "Regulador Buck step-down ajustable 3A",
        "family": "Reguladores",
        "description": "Convertidor DC-DC step-down, salida ajustable.",
        "datasheet_url": "https://www.ti.com/lit/ds/symlink/lm2596.pdf",
        "location": "B-02-3",
        "supplier": "DigiKey",
        "price_per_100": Decimal("1.1200"),
        "stock": 195,
        "tier": "C",
        "nato_score": "otan",
        "country_of_origin": "US",
    },
    {
        "mpn": "NE555",
        "sku": "NE555-DIP",
        "name": "Timer NE555",
        "family": "Discretos",
        "description": "Temporizador clásico NE555 en encapsulado DIP-8.",
        "datasheet_url": "https://www.ti.com/lit/ds/symlink/ne555.pdf",
        "location": "B-03-2",
        "supplier": "Farnell",
        "price_per_100": Decimal("0.4500"),
        "stock": 1200,
        "tier": "D",
        "nato_score": "100_otan",
        "country_of_origin": "US",
    },
    {
        "mpn": "MAX232",
        "sku": "MAX232-CPE",
        "name": "Interface RS232 dual",
        "family": "Comunicaciones",
        "description": "Conversor de niveles TTL/RS-232.",
        "datasheet_url": "https://www.analog.com/media/en/technical-documentation/data-sheets/max220-max249.pdf",
        "location": "B-05-1",
        "supplier": "Mouser",
        "price_per_100": Decimal("1.9000"),
        "stock": 68,
        "tier": "C",
        "nato_score": "otan",
        "country_of_origin": "US",
    },
    {
        "mpn": "STM32F407VGT6",
        "sku": "STM32F407",
        "name": "Microcontrolador ARM Cortex-M4",
        "family": "Microcontroladores",
        "description": "MCU de 32 bits, 168 MHz, 1 MB flash.",
        "datasheet_url": "https://www.st.com/resource/en/datasheet/stm32f407vg.pdf",
        "location": "C-02-1",
        "supplier": "DigiKey",
        "price_per_100": Decimal("12.4000"),
        "stock": 54,
        "tier": "A+",
        "nato_score": "allied_otan",
        "country_of_origin": "FR",
    },
    {
        "mpn": "ATmega328P",
        "sku": "ATMEGA328P",
        "name": "Microcontrolador AVR 8-bit",
        "family": "Microcontroladores",
        "description": "Microcontrolador clásico de la serie ATmega.",
        "datasheet_url": "https://ww1.microchip.com/downloads/en/DeviceDoc/Atmel-7810-Automotive-Microcontrollers-ATmega328P_Datasheet.pdf",
        "location": "C-03-1",
        "supplier": "Farnell",
        "price_per_100": Decimal("2.1500"),
        "stock": 92,
        "tier": "A",
        "nato_score": "otan",
        "country_of_origin": "US",
    },
    {
        "mpn": "GP2Y0E03",
        "sku": "GP2Y0E03",
        "name": "Sensor distancia IR 4-50cm",
        "family": "Sensores",
        "description": "Sensor de distancia infrarrojo de Sharp.",
        "datasheet_url": "https://www.pololu.com/file/0J717/gp2y0e03-datasheet.pdf",
        "location": "A-09-3",
        "supplier": "RS",
        "price_per_100": Decimal("9.2000"),
        "stock": 75,
        "tier": "B",
        "nato_score": "no_otan",
        "country_of_origin": "CN",
    },
]


def _generate_purchases(component_id, base_unit_cost: Decimal) -> list[ComponentPurchase]:  # type: ignore[no-untyped-def]
    """Return 3-6 ComponentPurchase rows spread across the last 12 months."""
    n_purchases = random.randint(3, 6)
    today = date.today()
    purchases: list[ComponentPurchase] = []
    for i in range(n_purchases):
        days_ago = random.randint(20, 360)
        purchased_at = today - timedelta(days=days_ago)
        quantity = random.choice([10, 25, 50, 100, 150, 250, 500, 750, 1000])
        jitter = Decimal(random.uniform(0.85, 1.15)).quantize(Decimal("0.01"))
        unit_cost = (base_unit_cost * jitter).quantize(Decimal("0.0001"))
        total_cost = (unit_cost * Decimal(quantity)).quantize(Decimal("0.0001"))
        supplier = random.choice(["DigiKey", "Farnell", "Mouser", "RS"])
        purchases.append(
            ComponentPurchase(
                component_id=component_id,
                purchased_at=purchased_at,
                quantity=quantity,
                supplier=supplier,
                unit_cost=unit_cost,
                total_cost=total_cost,
            )
        )
    return purchases


async def _seed(reset: bool) -> int:
    random.seed(42)  # deterministic seed so repeated runs are identical
    factory = get_session_factory()
    async with factory() as session:
        repo = SqlAlchemyComponentRepository(session)
        purchase_repo = SqlAlchemyComponentPurchaseRepository(session)

        if reset:
            await session.execute(
                text(
                    "TRUNCATE component_purchases, components "
                    "RESTART IDENTITY CASCADE"
                )
            )
            await session.commit()
        else:
            existing = await repo.list(filters=ComponentFilters(), page=1, page_size=1)
            if existing.total > 0:
                print(
                    f"Refusing to seed: {existing.total} components already exist. "
                    "Pass --reset to truncate and re-seed.",
                    file=sys.stderr,
                )
                return 2

        for sample in SAMPLE_COMPONENTS:
            component = await repo.save(
                Component(
                    mpn=sample["mpn"],
                    sku=sample["sku"],
                    name=sample["name"],
                    family=sample["family"],
                    description=sample["description"],
                    datasheet_url=sample["datasheet_url"],
                    location=sample["location"],
                    supplier=sample["supplier"],
                    price_per_100=sample["price_per_100"],
                    stock=sample["stock"],
                    tier=sample["tier"],
                    nato_score=sample["nato_score"],
                    country_of_origin=sample["country_of_origin"],
                )
            )
            for purchase in _generate_purchases(component.id, sample["price_per_100"] / Decimal("100")):
                await purchase_repo.save(purchase)

        await session.commit()
        print(f"Seeded {len(SAMPLE_COMPONENTS)} components with purchase history.")
        return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Seed sample components into a fresh DB.")
    parser.add_argument("--reset", action="store_true", help="Truncate first, then re-seed.")
    args = parser.parse_args(argv)
    return asyncio.run(_seed(reset=args.reset))


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
