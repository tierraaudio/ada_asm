"""SupplierStock domain entity — supplier-side inventory snapshot."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from uuid import UUID, uuid4


@dataclass
class SupplierStock:
    id: UUID = field(default_factory=uuid4)
    component_id: UUID | None = None
    supplier_id: UUID | None = None
    quantity: int = 0
    snapshot_at: date = field(default_factory=date.today)
    created_at: datetime | None = None
    updated_at: datetime | None = None
