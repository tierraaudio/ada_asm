"""StockEvent domain entity — a single inventory delta with kind discriminator.

Polymorphic owner via XOR — every event references exactly one of:
- `component_id`: kinds ``purchase`` (positive delta from a supplier) or
  ``consumption`` (negative delta from a project).
- `module_id`: kinds ``fabricated`` (positive delta when a module is built)
  or ``delivered`` (negative delta when shipped to a customer).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID, uuid4

StockEventKind = Literal["purchase", "consumption", "fabricated", "delivered"]


@dataclass
class StockEvent:
    id: UUID = field(default_factory=uuid4)
    # XOR: every event owns exactly one of these.
    component_id: UUID | None = None
    module_id: UUID | None = None
    kind: StockEventKind = "purchase"
    quantity: int = 0
    occurred_at: date = field(default_factory=date.today)
    notes: str | None = None
    # purchase + fabricated economics (positive deltas with cost data).
    supplier_id: UUID | None = None
    unit_cost: Decimal | None = None
    total_cost: Decimal | None = None
    currency: str = "EUR"
    # consumption-only (component usage attributed to a project).
    project_id: UUID | None = None
    project_name_snapshot: str | None = None
    # delivered-only (module units shipped to a Holded customer).
    customer_id_holded: str | None = None
    customer_name_snapshot: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
