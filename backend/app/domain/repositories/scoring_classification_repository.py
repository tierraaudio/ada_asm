"""Repository contract for `ScoringClassification`."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol
from uuid import UUID

from app.domain.entities.scoring_classification import ScoringClassification


class ScoringClassificationRepository(Protocol):
    async def list_for_scoring(
        self, nato_scoring_id: UUID
    ) -> list[ScoringClassification]: ...

    async def replace_for_scoring(
        self,
        nato_scoring_id: UUID,
        classifications: Sequence[ScoringClassification],
    ) -> list[ScoringClassification]:
        """Delete every classification of the scoring and insert the new list atomically."""
        ...

    async def save(self, classification: ScoringClassification) -> ScoringClassification: ...
