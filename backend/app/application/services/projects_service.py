"""Project (top-layer) service.

Mirrors `ModuleService` but adapted to a project root:

- CRUD with soft-delete (status -> Archived).
- Child-edge CRUD with XOR + duplicate validation. No cycle detection because
  projects are never hijos.
- Aggregates over the descendant tree (`project_children → module_children →
  components`).
- Price history (delegates to the repo's recursive walk).
- PATCH transitioning status to `Delivered` auto-fills `fecha_entrega_real`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import cast
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.services.modules_service import _worst_nato_score
from app.core.exceptions import (
    ChildAlreadyPresentError,
    InvalidChildReferenceError,
    ProjectNotFoundError,
)
from app.domain.entities.component import NatoScoreValue, TierValue
from app.domain.entities.customer import Customer
from app.domain.entities.project import Project, ProjectAggregates, ProjectStatus
from app.domain.entities.project_child import ProjectChild
from app.domain.entities.project_interest_link import ProjectInterestLink
from app.domain.repositories.project_repository import (
    PeriodLiteral,
    ProjectFilters,
    ProjectPage,
    ProjectPriceHistoryPoint,
)
from app.infrastructure.db.models.component import ComponentModel
from app.infrastructure.db.models.module import ModuleModel
from app.infrastructure.db.models.nato_scoring import ComponentNatoScoringModel
from app.infrastructure.db.models.supplier_price import SupplierPriceModel
from app.infrastructure.repositories.customer_repository import SqlAlchemyCustomerRepository
from app.infrastructure.repositories.project_interest_link_repository import (
    SqlAlchemyProjectInterestLinkRepository,
)
from app.infrastructure.repositories.project_repository import SqlAlchemyProjectRepository

logger = structlog.get_logger(__name__)


@dataclass
class ProjectCreate:
    code: str
    name: str
    description: str | None = None
    status: ProjectStatus = "Presupuestado"
    customer_id: UUID | None = None
    icon: str | None = None
    color: str | None = None
    tags: list[str] | None = None
    version: str | None = None
    fecha_inicio: date | None = None
    fecha_entrega_estimada: date | None = None
    fecha_entrega_real: date | None = None
    notas: str | None = None


@dataclass
class ProjectUpdate:
    """All fields optional — missing means 'leave alone'.

    The router translates its incoming payload into this dataclass; only the
    fields the user explicitly sent are non-None.
    """

    code: str | None = None
    name: str | None = None
    description: str | None = None
    status: ProjectStatus | None = None
    customer_id: UUID | None = None
    icon: str | None = None
    color: str | None = None
    tags: list[str] | None = None
    version: str | None = None
    fecha_inicio: date | None = None
    fecha_entrega_estimada: date | None = None
    fecha_entrega_real: date | None = None
    notas: str | None = None
    # Sentinel-aware: if the caller wants to clear `customer_id`, they pass
    # the explicit None via a request body field-set check at the router.


@dataclass
class AddProjectChildInput:
    child_module_id: UUID | None = None
    child_component_id: UUID | None = None
    quantity: int = 1
    notes: str | None = None
    sort_order: int = 0


@dataclass
class UpdateProjectChildInput:
    quantity: int | None = None
    notes: str | None = None
    sort_order: int | None = None


@dataclass
class ProjectDetailBundle:
    project: Project
    aggregates: ProjectAggregates
    children: list[ProjectChild]
    customer: Customer | None
    interest_links: list[ProjectInterestLink]


@dataclass
class _ComponentRollup:
    id: UUID
    stock: int
    nato_score: NatoScoreValue
    tier: TierValue
    expires_at: date | None = None


class ProjectService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = SqlAlchemyProjectRepository(session)
        self._customers = SqlAlchemyCustomerRepository(session)
        self._interest_links = SqlAlchemyProjectInterestLinkRepository(session)

    # ---------- CRUD ----------

    async def list_projects(
        self, *, filters: ProjectFilters, page: int, page_size: int
    ) -> ProjectPage:
        return await self._repo.list_projects(filters=filters, page=page, page_size=page_size)

    async def get(self, project_id: UUID) -> Project:
        p = await self._repo.get_by_id(project_id)
        if p is None:
            raise ProjectNotFoundError(f"project not found: {project_id}")
        return p

    async def get_detail(self, project_id: UUID) -> ProjectDetailBundle:
        project = await self.get(project_id)
        children = await self._repo.list_children(project_id)
        customer = (
            await self._customers.get_by_id(project.customer_id)
            if project.customer_id is not None
            else None
        )
        aggregates = await self.compute_aggregates(project_id)
        interest_links = await self._interest_links.list_for_project(project_id)
        return ProjectDetailBundle(
            project=project,
            aggregates=aggregates,
            children=children,
            customer=customer,
            interest_links=interest_links,
        )

    async def create(self, payload: ProjectCreate) -> Project:
        project = Project(
            code=payload.code,
            name=payload.name,
            description=payload.description,
            status=payload.status,
            customer_id=payload.customer_id,
            icon=payload.icon,
            color=payload.color,
            tags=list(payload.tags or []),
            version=payload.version,
            fecha_inicio=payload.fecha_inicio,
            fecha_entrega_estimada=payload.fecha_entrega_estimada,
            fecha_entrega_real=payload.fecha_entrega_real,
            notas=payload.notas,
        )
        # Auto-fill fecha_entrega_real when created directly as Completado.
        if project.status == "Completado" and project.fecha_entrega_real is None:
            project.fecha_entrega_real = date.today()
        saved = await self._repo.save(project)
        logger.info("project.created", project_id=str(saved.id), code=saved.code)
        return saved

    async def update(
        self,
        project_id: UUID,
        patch: ProjectUpdate,
        *,
        explicit_fecha_entrega_real: bool = False,
    ) -> Project:
        """Apply a partial update.

        `explicit_fecha_entrega_real` is True iff the caller explicitly sent
        the `fecha_entrega_real` field in the request body (even if it was
        null). Used to decide whether the Delivered auto-fill kicks in.
        """
        current = await self.get(project_id)
        previous_status = current.status

        if patch.code is not None:
            current.code = patch.code
        if patch.name is not None:
            current.name = patch.name
        if patch.description is not None:
            current.description = patch.description
        if patch.status is not None:
            current.status = patch.status
        if patch.customer_id is not None:
            current.customer_id = patch.customer_id
        if patch.icon is not None:
            current.icon = patch.icon
        if patch.color is not None:
            current.color = patch.color
        if patch.tags is not None:
            current.tags = list(patch.tags)
        if patch.version is not None:
            current.version = patch.version
        if patch.fecha_inicio is not None:
            current.fecha_inicio = patch.fecha_inicio
        if patch.fecha_entrega_estimada is not None:
            current.fecha_entrega_estimada = patch.fecha_entrega_estimada
        if patch.fecha_entrega_real is not None:
            current.fecha_entrega_real = patch.fecha_entrega_real
        if patch.notas is not None:
            current.notas = patch.notas

        # Auto-fill `fecha_entrega_real` when status transitions to Completado
        # and the caller didn't pass an explicit value.
        if (
            current.status == "Completado"
            and previous_status != "Completado"
            and not explicit_fecha_entrega_real
            and current.fecha_entrega_real is None
        ):
            current.fecha_entrega_real = date.today()

        return await self._repo.update(current)

    async def soft_delete(self, project_id: UUID) -> None:
        if not await self._repo.soft_delete(project_id):
            raise ProjectNotFoundError(f"project not found: {project_id}")
        logger.info("project.archived", project_id=str(project_id))

    # ---------- children ----------

    async def add_child(
        self, parent_project_id: UUID, payload: AddProjectChildInput
    ) -> ProjectChild:
        await self.get(parent_project_id)

        if (payload.child_module_id is None) == (payload.child_component_id is None):
            raise InvalidChildReferenceError(
                "exactly one of child_module_id / child_component_id must be set"
            )

        if payload.quantity < 1:
            raise InvalidChildReferenceError("quantity must be >= 1")

        if payload.child_module_id is not None:
            row = (
                await self._session.execute(
                    select(ModuleModel.id).where(ModuleModel.id == payload.child_module_id)
                )
            ).scalar_one_or_none()
            if row is None:
                raise InvalidChildReferenceError(
                    f"child module not found: {payload.child_module_id}"
                )
        else:
            assert payload.child_component_id is not None
            row = (
                await self._session.execute(
                    select(ComponentModel.id).where(ComponentModel.id == payload.child_component_id)
                )
            ).scalar_one_or_none()
            if row is None:
                raise InvalidChildReferenceError(
                    f"child component not found: {payload.child_component_id}"
                )

        if await self._repo.child_pair_exists(
            parent_project_id=parent_project_id,
            child_module_id=payload.child_module_id,
            child_component_id=payload.child_component_id,
        ):
            raise ChildAlreadyPresentError(
                "this child is already present — update quantity instead"
            )

        return await self._repo.add_child(
            ProjectChild(
                parent_project_id=parent_project_id,
                child_module_id=payload.child_module_id,
                child_component_id=payload.child_component_id,
                quantity=payload.quantity,
                notes=payload.notes,
                sort_order=payload.sort_order,
            )
        )

    async def update_child(
        self, parent_project_id: UUID, child_id: UUID, patch: UpdateProjectChildInput
    ) -> ProjectChild:
        await self.get(parent_project_id)
        existing = await self._repo.get_child(child_id)
        if existing is None or existing.parent_project_id != parent_project_id:
            raise ProjectNotFoundError(
                f"project_child not found: {child_id} (in project {parent_project_id})"
            )
        if patch.quantity is not None:
            if patch.quantity < 1:
                raise InvalidChildReferenceError("quantity must be >= 1")
            existing.quantity = patch.quantity
        if patch.notes is not None:
            existing.notes = patch.notes
        if patch.sort_order is not None:
            existing.sort_order = patch.sort_order
        return await self._repo.update_child(existing)

    async def remove_child(self, parent_project_id: UUID, child_id: UUID) -> None:
        existing = await self._repo.get_child(child_id)
        if existing is None or existing.parent_project_id != parent_project_id:
            return
        await self._repo.remove_child(child_id)

    # ---------- aggregates ----------

    async def _collect_component_rollups(
        self, project_id: UUID
    ) -> tuple[list[tuple[_ComponentRollup, int]], dict[UUID, Decimal]]:
        descendants = await self._repo.list_descendant_components(project_id)
        if not descendants:
            return [], {}

        qty_by_comp: dict[UUID, int] = {}
        for cid, q in descendants:
            qty_by_comp[cid] = qty_by_comp.get(cid, 0) + q
        comp_ids = list(qty_by_comp.keys())

        comp_rows = (
            await self._session.execute(
                select(
                    ComponentModel.id,
                    ComponentModel.stock,
                    ComponentModel.nato_score,
                    ComponentModel.tier,
                    ComponentModel.proveedor_preferente_id,
                ).where(ComponentModel.id.in_(comp_ids))
            )
        ).all()

        pref_by_comp: dict[UUID, UUID | None] = {
            cast(UUID, r[0]): cast(UUID | None, r[4]) for r in comp_rows
        }

        scoring_rows = (
            await self._session.execute(
                select(
                    ComponentNatoScoringModel.component_id,
                    ComponentNatoScoringModel.expires_at,
                )
                .where(ComponentNatoScoringModel.component_id.in_(comp_ids))
                .where(ComponentNatoScoringModel.status == "active")
            )
        ).all()
        expires_by_comp: dict[UUID, date] = {
            cast(UUID, r[0]): cast(date, r[1]) for r in scoring_rows
        }

        prices: dict[UUID, Decimal] = {}
        for comp_id, pref in pref_by_comp.items():
            if pref is None:
                continue
            row = (
                await self._session.execute(
                    select(SupplierPriceModel.price)
                    .where(SupplierPriceModel.component_id == comp_id)
                    .where(SupplierPriceModel.supplier_id == pref)
                    .where(SupplierPriceModel.qty_tier == 100)
                    .order_by(SupplierPriceModel.valid_from.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()
            if row is not None:
                prices[comp_id] = row

        rollups: list[tuple[_ComponentRollup, int]] = []
        for r in comp_rows:
            cid = cast(UUID, r[0])
            rollups.append(
                (
                    _ComponentRollup(
                        id=cid,
                        stock=cast(int, r[1]),
                        nato_score=cast(NatoScoreValue, r[2]),
                        tier=cast(TierValue, r[3]),
                        expires_at=expires_by_comp.get(cid),
                    ),
                    qty_by_comp[cid],
                )
            )
        return rollups, prices

    async def compute_aggregates(self, project_id: UUID) -> ProjectAggregates:
        rollups, prices = await self._collect_component_rollups(project_id)
        if not rollups:
            return ProjectAggregates(buildable_stock=0)

        total = Decimal("0")
        for comp, qty in rollups:
            price = prices.get(comp.id)
            if price is not None:
                total += price * qty

        scores = [c.nato_score for c, _ in rollups]
        worst_score = _worst_nato_score(scores)
        worst_tier = min(c.tier for c, _ in rollups)

        valid_expiries = [c.expires_at for c, _ in rollups if c.expires_at is not None]
        worst_expiry = min(valid_expiries) if valid_expiries else None

        buildable = await self._compute_buildable(project_id, rollups)

        return ProjectAggregates(
            precio_total=total if total > 0 else None,
            aggregated_nato_score=worst_score,
            aggregated_tier=worst_tier,
            aggregated_expires_at=worst_expiry,
            buildable_stock=buildable,
        )

    async def _compute_buildable(
        self,
        project_id: UUID,
        rollups: list[tuple[_ComponentRollup, int]],
    ) -> int:
        """How many full project units can be assembled given current stock.

        For each direct child edge:
        - Component leaf: `floor(component.stock / edge.quantity)`.
        - Module leaf: `floor(module.stock / edge.quantity)` — uses the
          module's already-assembled `stock` value. We do NOT recursively
          rebuild from module sub-components in this metric to keep parity
          with `ModuleService` and avoid runaway computation.

        Project buildable = MIN over direct children. Returns 0 if there are
        no direct children.
        """
        per_component_stock = {c.id: c.stock for c, _ in rollups}
        direct = await self._repo.list_children(project_id)
        if not direct:
            return 0

        # Hydrate module stocks for any direct module edges.
        module_edge_ids = [e.child_module_id for e in direct if e.child_module_id is not None]
        module_stocks: dict[UUID, int] = {}
        if module_edge_ids:
            rows = (
                await self._session.execute(
                    select(ModuleModel.id, ModuleModel.stock).where(
                        ModuleModel.id.in_(module_edge_ids)
                    )
                )
            ).all()
            module_stocks = {cast(UUID, r[0]): cast(int, r[1]) for r in rows}

        capacities: list[int] = []
        for edge in direct:
            qty = max(edge.quantity, 1)
            if edge.child_component_id is not None:
                stock = per_component_stock.get(edge.child_component_id, 0)
                capacities.append(stock // qty)
            elif edge.child_module_id is not None:
                stock = module_stocks.get(edge.child_module_id, 0)
                capacities.append(stock // qty)
        return min(capacities) if capacities else 0

    async def list_price_history(
        self, project_id: UUID, *, period: PeriodLiteral
    ) -> list[ProjectPriceHistoryPoint]:
        await self.get(project_id)
        return await self._repo.list_price_history(project_id=project_id, period=period)
