"""SupplierPrice domain entity — one quantity-tier of a supplier's price."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID, uuid4

QtyTier = Literal[1, 10, 100, 1000]


@dataclass
class SupplierPrice:
    id: UUID = field(default_factory=uuid4)
    component_id: UUID | None = None
    supplier_id: UUID | None = None
    qty_tier: QtyTier = 100
    price: Decimal = Decimal("0")
    valid_from: date = field(default_factory=date.today)
    created_at: datetime | None = None
    updated_at: datetime | None = None
