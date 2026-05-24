"""Component domain entity — the leaf of the asset tree.

`mpn` is the natural business key (case-insensitive unique). `tier` maps to
the criticality rubric (1=critical chips/MCUs, 4=commodity plastics/PCBs).
`nato_score` is the geopolitical-origin rubric (A+..F per the design).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID, uuid4

TierValue = Literal[1, 2, 3, 4]
NatoScoreValue = Literal["A+", "A", "B", "C", "D", "F"]


@dataclass
class Component:
    id: UUID = field(default_factory=uuid4)
    mpn: str = ""
    sku: str | None = None
    name: str = ""
    family: str = ""
    description: str | None = None
    datasheet_url: str | None = None
    location: str | None = None
    fabricante: str | None = None
    tipo_almacenamiento: str | None = None
    holded_id: str | None = None
    fecha_creacion: date | None = None
    notas: str | None = None
    stock: int = 0
    stock_min: int | None = None
    tier: TierValue = 3
    nato_score: NatoScoreValue = "C"
    country_of_origin: str | None = None
    proveedor_preferente_id: UUID | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    # Transient — populated by the list query via JOIN with supplier_prices
    # (preferred supplier x qty_tier=100 x latest valid_from). Never stored.
    current_price_per_100_eur: Decimal | None = None

    def effective_stock_min(self) -> int:
        """Default threshold is `tier * 5` when not explicitly set."""
        return self.stock_min if self.stock_min is not None else self.tier * 5
