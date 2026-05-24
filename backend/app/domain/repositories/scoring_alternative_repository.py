"""Repository contract for `ScoringAlternative`."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol
from uuid import UUID

from app.domain.entities.scoring_alternative import ScoringAlternative


class ScoringAlternativeRepository(Protocol):
    async def list_for_scoring(
        self, nato_scoring_id: UUID
    ) -> list[ScoringAlternative]: ...

    async def replace_for_scoring(
        self,
        nato_scoring_id: UUID,
        alternatives: Sequence[ScoringAlternative],
    ) -> list[ScoringAlternative]:
        """Delete every alternative of the scoring and insert the new list atomically."""
        ...

    async def save(self, alternative: ScoringAlternative) -> ScoringAlternative: ...
