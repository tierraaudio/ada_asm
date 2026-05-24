"""ScoringAlternative entity — an alternative component proposed in one scoring.

Each scoring owns its own list of alternatives (snapshot at scoring time).
No symmetry across scorings: the alternatives that a scoring of component A
proposes do not imply anything about what the scoring of B proposes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID, uuid4


@dataclass
class ScoringAlternative:
    id: UUID = field(default_factory=uuid4)
    nato_scoring_id: UUID | None = None
    alternative_component_id: UUID | None = None
    notes: str | None = None
    sort_order: int = 0
    created_at: datetime | None = None
    updated_at: datetime | None = None
