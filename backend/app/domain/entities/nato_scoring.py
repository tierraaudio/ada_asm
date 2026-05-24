"""ComponentNatoScoring entity — one OTAN classification execution.

Each scoring is an immutable audit record. A component has at most one
``status='active'`` scoring at any time (enforced by a partial unique index);
prior scorings become ``'archived'`` when a new one is created.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Literal
from uuid import UUID, uuid4

from app.domain.entities.component import NatoScoreValue, TierValue

NatoScoringStatus = Literal["active", "archived"]


@dataclass
class ComponentNatoScoring:
    id: UUID = field(default_factory=uuid4)
    component_id: UUID | None = None
    nato_score: NatoScoreValue = "C"
    tier: TierValue = 3
    classified_at: date = field(default_factory=date.today)
    expires_at: date = field(default_factory=date.today)
    classified_by_user_id: UUID | None = None
    status: NatoScoringStatus = "active"
    notes: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
