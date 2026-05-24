"""StockEvent domain entity — a single inventory delta with kind discriminator.

`kind` is either ``purchase`` (positive delta from a supplier) or
``consumption`` (negative delta from a project). The per-kind columns are
nullable at the DB level but enforced by CHECK constraints — see the
migration. The application layer should also validate before insert.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID, uuid4

StockEventKind = Literal["purchase", "consumption"]


@dataclass
class StockEvent:
    id: UUID = field(default_factory=uuid4)
    component_id: UUID | None = None
    kind: StockEventKind = "purchase"
    quantity: int = 0
    occurred_at: date = field(default_factory=date.today)
    notes: str | None = None
    # purchase-only
    supplier_id: UUID | None = None
    unit_cost: Decimal | None = None
    total_cost: Decimal | None = None
    currency: str = "EUR"
    # consumption-only
    project_id: UUID | None = None
    project_name_snapshot: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
