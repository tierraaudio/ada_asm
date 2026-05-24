"""Repository contract for the `ComponentNatoScoring` aggregate."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from app.domain.entities.nato_scoring import ComponentNatoScoring


class NatoScoringRepository(Protocol):
    async def get_active_for_component(
        self, component_id: UUID
    ) -> ComponentNatoScoring | None: ...

    async def list_for_component(
        self, component_id: UUID
    ) -> list[ComponentNatoScoring]: ...

    async def get_by_id(self, scoring_id: UUID) -> ComponentNatoScoring | None: ...

    async def archive_active(self, component_id: UUID) -> None:
        """Set ``status='archived'`` on the currently-active scoring (no-op if none)."""
        ...

    async def save(self, scoring: ComponentNatoScoring) -> ComponentNatoScoring: ...
