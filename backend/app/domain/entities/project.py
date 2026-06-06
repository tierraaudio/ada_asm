"""Project domain entity — the top of the asset tree (Project → Module → Component).

`code` is the natural business key (case-insensitive unique), user-typed, no
auto-generation. `status` follows a four-state lifecycle enforced at the DB
level. Soft-delete = transition to `Archived` — hard deletes are never a user
action in this US.

Aggregates (`precio_total`, `aggregated_*`, `buildable_stock`) are computed at
the service layer from the descendant tree; they are never persisted.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID, uuid4

from app.domain.entities.component import NatoScoreValue, TierValue

ProjectStatus = Literal[
    "Presupuestado", "Esperando", "En proceso", "Completado", "Archivado"
]


@dataclass
class Project:
    id: UUID = field(default_factory=uuid4)
    code: str = ""
    name: str = ""
    description: str | None = None
    status: ProjectStatus = "Presupuestado"
    customer_id: UUID | None = None
    icon: str | None = None  # single emoji char/cluster
    color: str | None = None  # hex `#rrggbb`
    tags: list[str] = field(default_factory=list)
    version: str | None = None
    fecha_inicio: date | None = None
    fecha_entrega_estimada: date | None = None
    fecha_entrega_real: date | None = None
    notas: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass
class ProjectAggregates:
    """Server-computed roll-ups exposed on the project detail/list endpoints.

    Mirrors `ModuleAggregates` semantics: never persisted, recomputed on
    every read from the descendant tree (project_children → module_children
    → components).
    """

    precio_total: Decimal | None = None
    aggregated_nato_score: NatoScoreValue | None = None
    aggregated_tier: TierValue | None = None
    aggregated_expires_at: date | None = None
    buildable_stock: int = 0
