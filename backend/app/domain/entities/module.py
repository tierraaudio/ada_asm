"""Module domain entity — the intermediate node of the asset tree.

A `Module` is a reusable assembly catalogue entry. Its children (other
modules or components) are tracked in `module_children` with explicit
`quantity`. Aggregates like total price, worst NATO/Tier, and the
buildable-stock derived metric are computed at the service layer, not
stored here.

`sku` is the natural business key (case-insensitive unique).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from app.domain.entities.component import NatoScoreValue, TierValue


@dataclass
class Module:
    id: UUID = field(default_factory=uuid4)
    sku: str = ""
    name: str = ""
    description: str | None = None
    version: str = "v1.0"
    fabricante: str | None = None
    location: str | None = None
    tipo_almacenamiento: str | None = None
    stock: int = 0
    notas: str | None = None
    fecha_creacion: date | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass
class ModuleAggregates:
    """Server-computed roll-ups exposed on the module detail/list endpoints.

    Never persisted — recomputed on every read so the values always reflect
    the current state of the child components and their scorings.
    """

    precio_total: Decimal | None = None
    aggregated_nato_score: NatoScoreValue | None = None
    aggregated_tier: TierValue | None = None
    aggregated_expires_at: date | None = None
    buildable_stock: int = 0
