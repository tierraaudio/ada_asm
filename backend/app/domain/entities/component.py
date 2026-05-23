"""Component domain entity — the leaf of the asset tree.

The `mpn` (manufacturer part number) is the business key. Persistence enforces
case-insensitive uniqueness on it. `tier` and `nato_score` are constrained to
their allowed enum values at the storage and API layers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID, uuid4

TierValue = Literal["A+", "A", "B", "C", "D"]
NatoScoreValue = Literal[
    "100_otan",
    "otan",
    "allied_otan",
    "neutral",
    "high_risk",
    "no_otan",
]


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
    supplier: str | None = None
    price_per_100: Decimal | None = None
    stock: int = 0
    tier: TierValue = "C"
    nato_score: NatoScoreValue = "neutral"
    country_of_origin: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
