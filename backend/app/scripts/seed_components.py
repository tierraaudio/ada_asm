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

from sqlalchemy import select, text

from app.application.services.nato_scoring_service import (
    AlternativeInput,
    ClassificationInput,
    CreateScoringInput,
    NatoScoringService,
)
from app.domain.entities.component import Component, NatoScoreValue, TierValue
from app.domain.entities.stock_event import StockEvent
from app.domain.entities.supplier import Supplier
from app.domain.entities.supplier_price import QtyTier, SupplierPrice
from app.domain.entities.supplier_stock import SupplierStock
from app.domain.repositories.component_repository import ComponentFilters
from app.infrastructure.db.models.user import UserModel
from app.infrastructure.db.session import get_session_factory
from app.infrastructure.repositories.component_repository import (
    SqlAlchemyComponentRepository,
)
from app.infrastructure.repositories.nato_scoring_repository import (
    SqlAlchemyNatoScoringRepository,
)
from app.infrastructure.repositories.scoring_alternative_repository import (
    SqlAlchemyScoringAlternativeRepository,
)
from app.infrastructure.repositories.scoring_classification_repository import (
    SqlAlchemyScoringClassificationRepository,
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

# Per-family realistic sub-parts to seed `scoring_classifications` with.
# Each tuple is (part_label, fabricante, country_of_origin, nato_score, verificado, notas).
FAMILY_CLASSIFICATIONS: dict[str, list[tuple[str, str, str, NatoScoreValue, bool, str]]] = {
    "Microcontroladores": [
        (
            "Chip principal",
            "STMicroelectronics",
            "FR",
            "A+",
            True,
            "Fabricado en Francia. Cumple con estándares OTAN.",
        ),
        ("Encapsulado plástico", "TDK", "DE", "A", True, "Material de bajo riesgo. Origen OTAN."),
        ("Sustrato cerámico", "Kyocera", "JP", "B", True, "Origen aliado OTAN."),
    ],
    "Sensores": [
        ("Chip sensor", "Bosch Sensortec", "DE", "A", True, "Sensor verificado de origen OTAN."),
        ("Encapsulado QFN", "Amkor", "KR", "B", True, "Encapsulado de un aliado OTAN."),
    ],
    "Condensadores": [
        ("Dieléctrico cerámico", "Murata", "JP", "B", True, "Material cerámico de origen aliado."),
        (
            "Terminales metálicos",
            "Local Plastics",
            "PL",
            "A+",
            True,
            "Terminales de origen verificado OTAN.",
        ),
    ],
    "Resistencias": [
        ("Elemento resistivo", "Yageo", "TW", "B", True, "Fabricación en Taiwán, aliado OTAN."),
        ("Encapsulado SMD", "Yageo", "TW", "B", True, "Mismo origen que el elemento resistivo."),
    ],
    "Diodos": [
        (
            "Cristal semiconductor",
            "Diodes Inc.",
            "US",
            "A+",
            True,
            "Silicio verificado de origen OTAN.",
        ),
        ("Encapsulado SMA", "ON Semiconductor", "US", "A+", True, "Origen verificado OTAN."),
    ],
    "Transistores": [
        ("Wafer semiconductor", "Infineon", "DE", "A", True, "Wafer alemán de origen OTAN."),
        ("Encapsulado TO-220", "Nexperia", "NL", "A", True, "Encapsulado de origen OTAN."),
        (
            "Leadframe metálico",
            "Local Plastics",
            "PL",
            "A+",
            True,
            "Aleación de origen verificado.",
        ),
    ],
    "Conectores": [
        ("Cuerpo plástico", "Amphenol", "US", "A+", True, "Plástico ignífugo de origen OTAN."),
        ("Contactos metálicos", "Molex", "US", "A+", True, "Aleación de cobre verificada."),
    ],
    "Fuentes de alimentación": [
        ("Chip regulador", "Texas Instruments", "US", "A+", True, "Silicio verificado OTAN."),
        ("Bobina interna", "Würth Elektronik", "DE", "A", True, "Inductor de origen OTAN."),
        ("Encapsulado SMD", "Local Plastics", "PL", "A+", True, "Encapsulado verificado."),
    ],
    "Módulos": [
        ("MCU principal", "Espressif", "CN", "D", False, "Origen no OTAN — revisar."),
        ("RF transceiver", "Espressif", "CN", "D", False, "Componente RF no verificado."),
        ("Antena PCB", "Local Plastics", "PL", "A+", True, "Antena impresa, origen OTAN."),
    ],
}


def _classifications_for(family: str) -> list[ClassificationInput]:
    template = FAMILY_CLASSIFICATIONS.get(
        family,
        [("Cuerpo principal", "Genérico", "ES", "B", True, "Componente sin desglose detallado.")],
    )
    return [
        ClassificationInput(
            part_label=label,
            fabricante=fab,
            country_of_origin=country,
            nato_score=score,
            verificado=verified,
            notas=note,
        )
        for (label, fab, country, score, verified, note) in template
    ]


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
    ),
    ComponentSeed(
        mpn="ATMEGA328P-PU",
        sku="MCU-014",
        name="ATmega328P - MCU AVR 8-bit DIP-28",
        family="Microcontroladores",
        description="MCU 8-bit, 32KB flash, 1KB EEPROM, encapsulado DIP-28.",
        location="G-A-15",
        fabricante="Microchip",
        tipo_almacenamiento="Bandeja",
        tier=1,
        nato_score="A+",
        country_of_origin="US",
        stock=78,
        stock_min=8,
        preferred_supplier="DigiKey",
        datasheet_url="https://ww1.microchip.com/downloads/en/DeviceDoc/Atmel-7810-Automotive-Microcontrollers-ATmega328P_Datasheet.pdf",
    ),
    ComponentSeed(
        mpn="RP2040",
        sku="MCU-029",
        name="RP2040 - MCU dual Cortex-M0+",
        family="Microcontroladores",
        description="MCU dual ARM Cortex-M0+ a 133 MHz, 264KB SRAM.",
        location="G-A-18",
        fabricante="Raspberry Pi",
        tipo_almacenamiento="Bobina",
        tier=1,
        nato_score="A",
        country_of_origin="GB",
        stock=120,
        stock_min=10,
        preferred_supplier="Mouser",
        datasheet_url="https://datasheets.raspberrypi.com/rp2040/rp2040-datasheet.pdf",
    ),
    ComponentSeed(
        mpn="W25Q128JVSIQ",
        sku="MEM-007",
        name="W25Q128 - Flash SPI 128Mbit",
        family="Microcontroladores",
        description="Memoria Flash SPI de 128 Mbit (16 MB), SOIC-8.",
        location="G-A-19",
        fabricante="Winbond",
        tipo_almacenamiento="Bobina",
        tier=1,
        nato_score="B",
        country_of_origin="TW",
        stock=4,
        stock_min=10,
        preferred_supplier="DigiKey",
        datasheet_url="https://www.winbond.com/resource-files/w25q128jv_revh.pdf",
    ),
    ComponentSeed(
        mpn="MPU-6050",
        sku="SEN-031",
        name="MPU-6050 - IMU 6 ejes",
        family="Sensores",
        description="Acelerómetro + giroscopio 6 ejes I2C.",
        location="G-S-22",
        fabricante="TDK InvenSense",
        tipo_almacenamiento="Gaveta",
        tier=2,
        nato_score="C",
        country_of_origin="CN",
        stock=45,
        stock_min=10,
        preferred_supplier="Mouser",
        datasheet_url="https://invensense.tdk.com/wp-content/uploads/2015/02/MPU-6000-Datasheet1.pdf",
    ),
    ComponentSeed(
        mpn="DHT22",
        sku="SEN-042",
        name="DHT22 - Sensor temperatura/humedad",
        family="Sensores",
        description="Sensor digital de temperatura y humedad single-wire.",
        location="G-S-23",
        fabricante="Aosong",
        tipo_almacenamiento="Bandeja",
        tier=2,
        nato_score="D",
        country_of_origin="CN",
        stock=8,
        stock_min=10,
        preferred_supplier="Farnell",
        datasheet_url="https://www.sparkfun.com/datasheets/Sensors/Temperature/DHT22.pdf",
    ),
    ComponentSeed(
        mpn="VL53L1X",
        sku="SEN-058",
        name="VL53L1X - ToF láser 4m",
        family="Sensores",
        description="Sensor de distancia láser ToF, rango hasta 4 m, I2C.",
        location="G-S-25",
        fabricante="STMicroelectronics",
        tipo_almacenamiento="Gaveta",
        tier=2,
        nato_score="A+",
        country_of_origin="FR",
        stock=35,
        stock_min=10,
        preferred_supplier="DigiKey",
        datasheet_url="https://www.st.com/resource/en/datasheet/vl53l1x.pdf",
    ),
    ComponentSeed(
        mpn="LM358",
        sku="IC-203",
        name="LM358 - Op-amp doble SOIC-8",
        family="Microcontroladores",
        description="Amplificador operacional dual, alimentación única.",
        location="G-A-30",
        fabricante="Texas Instruments",
        tipo_almacenamiento="Bobina",
        tier=1,
        nato_score="A+",
        country_of_origin="US",
        stock=620,
        stock_min=30,
        preferred_supplier="TME",
        datasheet_url="https://www.ti.com/lit/ds/symlink/lm358.pdf",
    ),
    ComponentSeed(
        mpn="AMS1117-3.3",
        sku="REG-027",
        name="AMS1117 - LDO 3.3V 1A SOT-223",
        family="Fuentes de alimentación",
        description="Regulador LDO de 3.3 V, 1 A, encapsulado SOT-223.",
        location="G-P-10",
        fabricante="Advanced Monolithic Systems",
        tipo_almacenamiento="Bobina",
        tier=3,
        nato_score="C",
        country_of_origin="CN",
        stock=400,
        stock_min=40,
        preferred_supplier="TME",
        datasheet_url="https://www.advanced-monolithic.com/pdf/ds1117.pdf",
    ),
    ComponentSeed(
        mpn="TPS5430",
        sku="REG-058",
        name="TPS5430 - Buck 5.5-36V → ajustable 3A",
        family="Fuentes de alimentación",
        description="Convertidor DC-DC, entrada hasta 36 V, salida ajustable.",
        location="G-P-12",
        fabricante="Texas Instruments",
        tipo_almacenamiento="Bandeja",
        tier=3,
        nato_score="A+",
        country_of_origin="US",
        stock=22,
        stock_min=10,
        preferred_supplier="DigiKey",
        datasheet_url="https://www.ti.com/lit/ds/symlink/tps5430.pdf",
    ),
    ComponentSeed(
        mpn="CR2032",
        sku="BAT-006",
        name="CR2032 - Pila botón de litio 3V",
        family="Fuentes de alimentación",
        description="Pila botón de litio 3 V, 220 mAh.",
        location="G-P-14",
        fabricante="Panasonic",
        tipo_almacenamiento="Bandeja",
        tier=4,
        nato_score="A",
        country_of_origin="JP",
        stock=180,
        stock_min=40,
        preferred_supplier="Farnell",
        datasheet_url="https://industrial.panasonic.com/cdbs/www-data/pdf/AAB4000/AAB4000C20.pdf",
    ),
    ComponentSeed(
        mpn="RC0805FR-074K7",
        sku="RES-204",
        name="Resistencia 4.7 kΩ 0805 1%",
        family="Resistencias",
        description="SMD 0805, 4.7 kΩ, ±1%, 1/8 W.",
        location="G-S-12",
        fabricante="Yageo",
        tipo_almacenamiento="Bobina",
        tier=3,
        nato_score="A+",
        country_of_origin="TW",
        stock=1500,
        stock_min=100,
        preferred_supplier="TME",
        datasheet_url="https://www.yageo.com/upload/media/product/productsearch/datasheet/rchip/PYu-RC_Group_51_RoHS_L_11.pdf",
    ),
    ComponentSeed(
        mpn="RC0805JR-07330R",
        sku="RES-301",
        name="Resistencia 330 Ω 0805 5%",
        family="Resistencias",
        description="SMD 0805, 330 Ω, ±5%, 1/8 W.",
        location="G-S-13",
        fabricante="Yageo",
        tipo_almacenamiento="Bobina",
        tier=3,
        nato_score="A+",
        country_of_origin="TW",
        stock=950,
        stock_min=100,
        preferred_supplier="TME",
        datasheet_url="https://www.yageo.com/upload/media/product/productsearch/datasheet/rchip/PYu-RC_Group_51_RoHS_L_11.pdf",
    ),
    ComponentSeed(
        mpn="CL10A106KP8NNNC",
        sku="CAP-118",
        name="Condensador cerámico 10µF 10V X5R 0603",
        family="Condensadores",
        description="MLCC X5R 0603, 10 µF, 10 V, ±10%.",
        location="G-C-10",
        fabricante="Samsung",
        tipo_almacenamiento="Bobina",
        tier=3,
        nato_score="B",
        country_of_origin="KR",
        stock=2200,
        stock_min=200,
        preferred_supplier="Mouser",
        datasheet_url="https://product.samsungsem.com/mlcc/CL10A106KP8NNNC.do",
    ),
    ComponentSeed(
        mpn="EEUFM1H101",
        sku="CAP-227",
        name="Condensador electrolítico 100µF 50V",
        family="Condensadores",
        description="Electrolítico aluminio radial, 100 µF, 50 V, 105 °C.",
        location="G-C-12",
        fabricante="Panasonic",
        tipo_almacenamiento="Bandeja",
        tier=3,
        nato_score="A",
        country_of_origin="JP",
        stock=320,
        stock_min=60,
        preferred_supplier="Farnell",
        datasheet_url="https://industrial.panasonic.com/cdbs/www-data/pdf/RDF0000/ABA0000C1265.pdf",
    ),
    ComponentSeed(
        mpn="SS14",
        sku="DIO-141",
        name="SS14 - Diodo Schottky 1A 40V",
        family="Diodos",
        description="Diodo Schottky, encapsulado SMA, 1 A, 40 V.",
        location="G-T-22",
        fabricante="Vishay",
        tipo_almacenamiento="Bobina",
        tier=3,
        nato_score="A+",
        country_of_origin="DE",
        stock=480,
        stock_min=80,
        preferred_supplier="DigiKey",
        datasheet_url="https://www.vishay.com/docs/88751/ss12.pdf",
    ),
    ComponentSeed(
        mpn="1N4148W",
        sku="DIO-203",
        name="1N4148 - Diodo conmutación rápida SOD-123",
        family="Diodos",
        description="Diodo de conmutación, 100 V, 200 mA, SOD-123.",
        location="G-T-23",
        fabricante="ON Semiconductor",
        tipo_almacenamiento="Bobina",
        tier=3,
        nato_score="A+",
        country_of_origin="US",
        stock=2300,
        stock_min=200,
        preferred_supplier="TME",
        datasheet_url="https://www.onsemi.com/pdf/datasheet/1n4148w-d.pdf",
    ),
    ComponentSeed(
        mpn="2N7002",
        sku="TRN-098",
        name="2N7002 - MOSFET N 60V 115mA SOT-23",
        family="Transistores",
        description="MOSFET N pequeño señal, 60 V, 115 mA, SOT-23.",
        location="G-T-30",
        fabricante="Nexperia",
        tipo_almacenamiento="Bobina",
        tier=3,
        nato_score="A",
        country_of_origin="NL",
        stock=900,
        stock_min=100,
        preferred_supplier="Farnell",
        datasheet_url="https://assets.nexperia.com/documents/data-sheet/2N7002.pdf",
    ),
    ComponentSeed(
        mpn="BC547BTA",
        sku="TRN-145",
        name="BC547 - Transistor NPN TO-92",
        family="Transistores",
        description="Transistor BJT NPN de propósito general, TO-92.",
        location="G-T-31",
        fabricante="ON Semiconductor",
        tipo_almacenamiento="Bandeja",
        tier=3,
        nato_score="A+",
        country_of_origin="US",
        stock=550,
        stock_min=100,
        preferred_supplier="TME",
        datasheet_url="https://www.onsemi.com/pdf/datasheet/bc547-d.pdf",
    ),
    ComponentSeed(
        mpn="61300411121",
        sku="CON-119",
        name="Pin header 2.54mm 1x4",
        family="Conectores",
        description="Tira de pines macho 1x4, paso 2.54 mm, recta.",
        location="G-N-08",
        fabricante="Würth Elektronik",
        tipo_almacenamiento="Bandeja",
        tier=4,
        nato_score="A+",
        country_of_origin="DE",
        stock=320,
        stock_min=60,
        preferred_supplier="Farnell",
        datasheet_url="https://www.we-online.com/components/products/datasheet/61300411121.pdf",
    ),
    ComponentSeed(
        mpn="Molex 22-23-2041",
        sku="CON-205",
        name="KK 254 - Header THT 4 pines",
        family="Conectores",
        description="Conector Molex KK 254 macho recto, 4 pines.",
        location="G-N-12",
        fabricante="Molex",
        tipo_almacenamiento="Bandeja",
        tier=4,
        nato_score="A",
        country_of_origin="US",
        stock=160,
        stock_min=40,
        preferred_supplier="DigiKey",
        datasheet_url="https://www.molex.com/pdm_docs/sd/022232041_sd.pdf",
    ),
    ComponentSeed(
        mpn="RPi-Pico-W",
        sku="MOD-091",
        name="Raspberry Pi Pico W - MCU WiFi",
        family="Módulos",
        description="Módulo RP2040 + WiFi 2.4 GHz, USB-C.",
        location="G-M-04",
        fabricante="Raspberry Pi",
        tipo_almacenamiento="Bandeja",
        tier=1,
        nato_score="A",
        country_of_origin="GB",
        stock=18,
        stock_min=10,
        preferred_supplier="Mouser",
        datasheet_url="https://datasheets.raspberrypi.com/picow/pico-w-datasheet.pdf",
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
                    "TRUNCATE scoring_alternatives, scoring_classifications, "
                    "component_nato_scorings, stock_events, supplier_stocks, "
                    "supplier_prices, suppliers, components "
                    "RESTART IDENTITY CASCADE"
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
        saved_components: list[tuple[Component, ComponentSeed]] = []
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
                    notas=None,
                    stock=sample.stock,
                    stock_min=sample.stock_min,
                    tier=sample.tier,
                    nato_score=sample.nato_score,
                    country_of_origin=sample.country_of_origin,
                    proveedor_preferente_id=supplier_by_name[sample.preferred_supplier],
                )
            )
            saved_components.append((component, sample))

            # Supplier prices: 4 snapshots (today + 2m + 4m + 6m ago) for every
            # supplier x every qty_tier — enough points for the histórico chart.
            base_unit_cost_by_supplier = {
                supplier: Decimal(str(round(random.uniform(0.50, 12.00), 2)))
                for supplier in SUPPLIER_NAMES
            }
            for supplier_name in SUPPLIER_NAMES:
                base = base_unit_cost_by_supplier[supplier_name]
                for months_ago in (6, 4, 2, 0):
                    valid_from = today - timedelta(days=months_ago * 30)
                    # Slight monthly drift (±8 %) so the chart has visible motion.
                    drift = Decimal(str(round(random.uniform(0.92, 1.08), 4)))
                    snapshot_base = (base * drift).quantize(Decimal("0.0001"))
                    for qty_tier in cast(list[QtyTier], [1, 10, 100, 1000]):
                        await prices_repo.save(
                            SupplierPrice(
                                component_id=component.id,
                                supplier_id=supplier_by_name[supplier_name],
                                qty_tier=qty_tier,
                                price=_qty_tier_price(snapshot_base, qty_tier),
                                valid_from=valid_from,
                            )
                        )

            # Supplier stock snapshots: 9 weekly snapshots over the last 60 days
            # per supplier. The most recent snapshot also drives the StockStatus
            # badge logic (rojo / ámbar / verde) on the list page.
            local_out = sample.stock == 0
            for supplier_name in SUPPLIER_NAMES:
                # Pick a baseline that's coherent with the local stock signal.
                if local_out and supplier_name in {"Farnell", "RS"}:
                    baseline = 0
                else:
                    baseline = random.randint(80, 320)
                for days_ago in (56, 49, 42, 35, 28, 21, 14, 7, 0):
                    # Random walk around baseline so the chart is non-trivial.
                    jitter = random.randint(-40, 40) if baseline > 0 else 0
                    quantity = max(0, baseline + jitter)
                    await stocks_repo.save(
                        SupplierStock(
                            component_id=component.id,
                            supplier_id=supplier_by_name[supplier_name],
                            quantity=quantity,
                            snapshot_at=today - timedelta(days=days_ago),
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

        # ---- NATO scorings (one active per component) ------------------------
        # Need an admin user for the audit trail. Fall back to None if no users.
        admin_row = (
            await session.execute(
                select(UserModel).where(UserModel.global_role == "admin").limit(1)
            )
        ).scalar_one_or_none()
        classified_by = admin_row.id if admin_row else None

        scoring_service = NatoScoringService(
            session=session,
            components=components_repo,
            scorings=SqlAlchemyNatoScoringRepository(session),
            classifications=SqlAlchemyScoringClassificationRepository(session),
            alternatives=SqlAlchemyScoringAlternativeRepository(session),
        )

        # Pre-index components by family so each scoring's `alternatives` block
        # can pick 2-3 same-family candidates without re-querying.
        by_family: dict[str, list[Component]] = {}
        for comp, sample in saved_components:
            by_family.setdefault(sample.family, []).append(comp)

        for component, sample in saved_components:
            classified_at = today - timedelta(days=random.randint(0, 60))
            alternatives_pool = [
                c for c in by_family.get(sample.family, []) if c.id != component.id
            ]
            picked = random.sample(alternatives_pool, k=min(3, len(alternatives_pool)))
            await scoring_service.create_scoring(
                component_id=component.id,
                payload=CreateScoringInput(
                    nato_score=sample.nato_score,
                    tier=sample.tier,
                    classified_at=classified_at,
                    classified_by_user_id=classified_by,
                    notes=f"Clasificación inicial seedeada para {sample.mpn}.",
                    classifications=_classifications_for(sample.family),
                    alternatives=[
                        AlternativeInput(alternative_component_id=alt.id) for alt in picked
                    ],
                ),
            )

        await session.commit()
        print(
            f"Seeded {len(SAMPLE_COMPONENTS)} components, "
            f"{len(SUPPLIER_NAMES)} suppliers, prices, stocks, stock events "
            f"and 1 active NATO scoring + classifications/alternatives per component."
        )
        return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Seed sample components into a fresh DB.")
    parser.add_argument("--reset", action="store_true", help="Truncate first, then re-seed.")
    args = parser.parse_args(argv)
    return asyncio.run(_seed(reset=args.reset))


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
