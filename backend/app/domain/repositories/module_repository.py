"""Repository contract for the `Module` aggregate.

The service layer is responsible for cycle detection, XOR validation, and
aggregate computation. The repository only translates queries → SQL and
raises `ModuleSkuAlreadyRegisteredError` on the case-insensitive sku unique
constraint violation.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Literal, Protocol
from uuid import UUID

from app.domain.entities.module import Module
from app.domain.entities.module_child import ModuleChild

PeriodLiteral = Literal["week", "month", "year"]


@dataclass
class ModuleFilters:
    """Query filters for `list`. All optional; combined with AND.

    `q` matches case-insensitively against sku / name / description.
    """

    q: str | None = None


@dataclass
class ModulePage:
    items: list[Module]
    total: int
    page: int
    page_size: int


@dataclass
class ModulePriceHistoryPoint:
    date: date
    price: Decimal


class ModuleRepository(Protocol):
    """Persistence contract for modules + their child edges."""

    # ---------- modules ----------

    async def list_modules(
        self,
        *,
        filters: ModuleFilters,
        page: int,
        page_size: int,
    ) -> ModulePage: ...

    async def get_by_id(self, module_id: UUID) -> Module | None: ...

    async def get_by_sku(self, sku: str) -> Module | None: ...

    async def save(self, module: Module) -> Module: ...

    async def update(self, module: Module) -> Module: ...

    async def delete(self, module_id: UUID) -> bool:
        """Returns True if a row was deleted, False if no row matched."""
        ...

    # ---------- children (DAG edges) ----------

    async def list_children(self, parent_module_id: UUID) -> list[ModuleChild]: ...

    async def list_parents(self, child_module_id: UUID) -> list[Module]:
        """Modules that hold this module as a direct child."""
        ...

    async def list_parents_of_component(self, child_component_id: UUID) -> list[Module]:
        """Modules that hold this component as a direct child."""
        ...

    async def get_child(self, child_id: UUID) -> ModuleChild | None: ...

    async def add_child(self, child: ModuleChild) -> ModuleChild: ...

    async def update_child(self, child: ModuleChild) -> ModuleChild: ...

    async def remove_child(self, child_id: UUID) -> bool: ...

    async def child_pair_exists(
        self,
        *,
        parent_module_id: UUID,
        child_module_id: UUID | None,
        child_component_id: UUID | None,
    ) -> bool: ...

    async def check_cycle(
        self,
        *,
        parent_module_id: UUID,
        candidate_child_module_id: UUID,
    ) -> bool:
        """Returns True if adding (parent, candidate_child) would close a cycle.

        Implementation runs a `WITH RECURSIVE` query over `module_children`
        starting from `candidate_child_module_id`; returns True if
        `parent_module_id` is reachable as a descendant (or equals the
        candidate itself).
        """
        ...

    # ---------- aggregate primitives ----------

    async def list_descendant_components(
        self,
        module_id: UUID,
    ) -> list[tuple[UUID, int]]:
        """Flatten all component leaves under `module_id`.

        Returns `(component_id, propagated_quantity)` tuples. The propagated
        quantity is the product of edge quantities along the path from the
        root module to each leaf. Used by the service to compute aggregates.
        """
        ...

    async def list_price_history(
        self,
        *,
        module_id: UUID,
        period: PeriodLiteral,
    ) -> list[ModulePriceHistoryPoint]: ...
