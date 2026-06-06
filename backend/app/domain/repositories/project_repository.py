"""Repository contract for the `Project` aggregate + its DAG edges.

Mirrors `ModuleRepository` shape. No cycle detection — projects are never
hijos so cycles are structurally impossible.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Literal, Protocol
from uuid import UUID

from app.domain.entities.project import Project, ProjectStatus
from app.domain.entities.project_child import ProjectChild

PeriodLiteral = Literal["week", "month", "year"]


@dataclass
class ProjectFilters:
    """Query filters for `list_projects`. Combined with AND.

    `q` matches case-insensitively against code / name / customer.name.

    The list endpoint defaults to excluding `Archived` rows. The repository
    itself is honest about it: when `statuses` is None and `include_archived`
    is False, exclude Archived; when `statuses` is explicit, that list is
    final (the caller is responsible for whether Archived is in it).
    """

    q: str | None = None
    statuses: list[ProjectStatus] | None = None
    include_archived: bool = False
    customer_ids: list[UUID] = field(default_factory=list)


@dataclass
class ProjectPage:
    items: list[Project]
    total: int
    page: int
    page_size: int


@dataclass
class ProjectPriceHistoryPoint:
    date: date
    price: Decimal


class ProjectRepository(Protocol):
    """Persistence contract for projects + their child edges."""

    # ---------- projects ----------

    async def list_projects(
        self,
        *,
        filters: ProjectFilters,
        page: int,
        page_size: int,
    ) -> ProjectPage: ...

    async def get_by_id(self, project_id: UUID) -> Project | None: ...

    async def get_by_code(self, code: str) -> Project | None: ...

    async def save(self, project: Project) -> Project: ...

    async def update(self, project: Project) -> Project: ...

    async def soft_delete(self, project_id: UUID) -> bool:
        """Sets status='Archived'. Returns True if the project existed."""
        ...

    # ---------- children (DAG edges) ----------

    async def list_children(self, parent_project_id: UUID) -> list[ProjectChild]: ...

    async def get_child(self, child_id: UUID) -> ProjectChild | None: ...

    async def add_child(self, child: ProjectChild) -> ProjectChild: ...

    async def update_child(self, child: ProjectChild) -> ProjectChild: ...

    async def remove_child(self, child_id: UUID) -> bool: ...

    async def child_pair_exists(
        self,
        *,
        parent_project_id: UUID,
        child_module_id: UUID | None,
        child_component_id: UUID | None,
    ) -> bool: ...

    # ---------- cross-feature lookups ("projects-using") ----------

    async def list_for_component(self, child_component_id: UUID) -> list[Project]:
        """Projects that hold this component as a direct child."""
        ...

    async def list_for_module(self, child_module_id: UUID) -> list[Project]:
        """Projects that hold this module as a direct child."""
        ...

    # ---------- aggregate primitives ----------

    async def list_descendant_components(
        self,
        project_id: UUID,
    ) -> list[tuple[UUID, int]]:
        """Flatten all component leaves under a project.

        Descends through `project_children → module_children` until reaching
        component leaves. Returns `(component_id, propagated_quantity)`.
        """
        ...

    async def list_price_history(
        self,
        *,
        project_id: UUID,
        period: PeriodLiteral,
    ) -> list[ProjectPriceHistoryPoint]: ...
