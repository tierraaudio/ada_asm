"""Repository contract for the `Component` aggregate."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from app.domain.entities.component import Component, NatoScoreValue, TierValue


@dataclass
class ComponentFilters:
    """Query filters for `list`. All optional; combine with AND, search with OR."""

    q: str | None = None
    family: str | None = None
    supplier: str | None = None
    tier: TierValue | None = None
    nato_score: NatoScoreValue | None = None


@dataclass
class ComponentPage:
    items: list[Component]
    total: int
    page: int
    page_size: int


class ComponentRepository(Protocol):
    async def list(
        self,
        *,
        filters: ComponentFilters,
        page: int,
        page_size: int,
    ) -> ComponentPage: ...

    async def get_by_id(self, component_id: UUID) -> Component | None: ...

    async def get_by_mpn(self, mpn: str) -> Component | None: ...

    async def save(self, component: Component) -> Component: ...

    async def update(self, component: Component) -> Component: ...

    async def delete(self, component_id: UUID) -> bool:
        """Returns True if a row was deleted, False if no row matched."""
        ...
