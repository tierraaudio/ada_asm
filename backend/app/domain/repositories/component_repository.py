"""Repository contract for the `Component` aggregate."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from app.domain.entities.component import Component, NatoScoreValue, TierValue


@dataclass
class ComponentFilters:
    """Query filters for `list`. All optional; combined with AND.

    `q` matches case-insensitively against mpn / sku / name / family.
    `families`, `suppliers`, `tiers`, `nato_scores` are multi-value: an entry
    matches when its column is one of the provided values. `supplier` here
    refers to the preferred supplier id (`proveedor_preferente_id`).
    """

    q: str | None = None
    families: list[str] | None = None
    supplier_ids: list[UUID] | None = None
    tiers: list[TierValue] | None = None
    nato_scores: list[NatoScoreValue] | None = None
    locations: list[str] | None = None


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
