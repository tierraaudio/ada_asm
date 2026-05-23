"""ComponentPurchase domain entity — one purchase event."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID, uuid4


@dataclass
class ComponentPurchase:
    id: UUID = field(default_factory=uuid4)
    component_id: UUID = field(default_factory=uuid4)
    purchased_at: date | None = None
    quantity: int = 0
    supplier: str = ""
    unit_cost: Decimal = Decimal("0")
    total_cost: Decimal = Decimal("0")
    currency: str = "EUR"
    created_at: datetime | None = None
    updated_at: datetime | None = None
