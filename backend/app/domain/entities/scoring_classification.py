"""ScoringClassification entity — a sub-part analysed in one NATO scoring.

Each row belongs to a single scoring and represents one breakdown line
("Chip principal STM32...", "Encapsulado plástico", …). The optional
`reference_component_id` XOR `reference_url` lets the sub-part link to
another component in our catalogue, an external URL, or stay as plain text.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID, uuid4

from app.domain.entities.component import NatoScoreValue


@dataclass
class ScoringClassification:
    id: UUID = field(default_factory=uuid4)
    nato_scoring_id: UUID | None = None
    part_label: str = ""
    fabricante: str | None = None
    country_of_origin: str | None = None
    nato_score: NatoScoreValue | None = None
    verificado: bool = False
    notas: str | None = None
    reference_component_id: UUID | None = None
    reference_url: str | None = None
    sort_order: int = 0
    created_at: datetime | None = None
    updated_at: datetime | None = None
