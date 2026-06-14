"""SQLAlchemy-backed implementation of `ProjectRepository`.

Mirrors `SqlAlchemyModuleRepository` (filters/pagination/child CRUD, recursive
descendant walk) but without cycle detection — projects can't be hijos so
cycles are structurally impossible.

The list endpoint defaults to excluding `Archived` rows; the filter struct
makes this explicit so the router doesn't have to second-guess.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import cast
from uuid import UUID

from sqlalchemy import delete, func, or_, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ProjectCodeAlreadyRegisteredError
from app.domain.entities.project import Project, ProjectStatus
from app.domain.entities.project_child import ProjectChild
from app.domain.repositories.project_repository import (
    PeriodLiteral,
    ProjectFilters,
    ProjectPage,
    ProjectPriceHistoryPoint,
)
from app.infrastructure.db.models.component import ComponentModel
from app.infrastructure.db.models.customer import CustomerModel
from app.infrastructure.db.models.project import ProjectModel
from app.infrastructure.db.models.project_child import ProjectChildModel
from app.infrastructure.db.models.supplier_price import SupplierPriceModel


def _to_entity(row: ProjectModel) -> Project:
    return Project(
        id=row.id,
        code=row.code,
        name=row.name,
        description=row.description,
        status=cast(ProjectStatus, row.status),
        customer_id=row.customer_id,
        icon=row.icon,
        color=row.color,
        tags=list(row.tags or []),
        version=row.version,
        fecha_inicio=row.fecha_inicio,
        fecha_entrega_estimada=row.fecha_entrega_estimada,
        fecha_entrega_real=row.fecha_entrega_real,
        notas=row.notas,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _child_to_entity(row: ProjectChildModel) -> ProjectChild:
    return ProjectChild(
        id=row.id,
        parent_project_id=row.parent_project_id,
        child_module_id=row.child_module_id,
        child_component_id=row.child_component_id,
        quantity=row.quantity,
        sort_order=row.sort_order,
        notes=row.notes,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _is_code_unique_violation(exc: IntegrityError) -> bool:
    return "uq_projects_code_lower" in str(exc.orig).lower()


def _period_cutoff(period: PeriodLiteral) -> date:
    today = date.today()
    if period == "week":
        return today - timedelta(days=7)
    if period == "month":
        return today - timedelta(days=30)
    return today - timedelta(days=365)


class SqlAlchemyProjectRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ---------- projects ----------

    async def list_projects(
        self,
        *,
        filters: ProjectFilters,
        page: int,
        page_size: int,
    ) -> ProjectPage:
        stmt = select(ProjectModel)
        joined_customer = False
        if filters.q is not None and filters.q.strip():
            needle = f"%{filters.q.strip().lower()}%"
            stmt = stmt.outerjoin(CustomerModel, CustomerModel.id == ProjectModel.customer_id)
            joined_customer = True
            stmt = stmt.where(
                or_(
                    func.lower(ProjectModel.code).like(needle),
                    func.lower(ProjectModel.name).like(needle),
                    func.lower(CustomerModel.name).like(needle),
                )
            )

        if filters.statuses is not None:
            # Explicit list — caller controls Archived inclusion.
            stmt = stmt.where(ProjectModel.status.in_(list(filters.statuses)))
        elif not filters.include_archived:
            # Default behaviour — exclude Archived rows.
            stmt = stmt.where(ProjectModel.status != "Archivado")

        if filters.customer_ids:
            stmt = stmt.where(ProjectModel.customer_id.in_(list(filters.customer_ids)))

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await self._session.execute(count_stmt)).scalar_one()
        rows_stmt = (
            stmt.order_by(ProjectModel.created_at.desc())
            .limit(page_size)
            .offset((page - 1) * page_size)
        )
        if joined_customer:
            # Avoid duplicate rows from the JOIN when the same project would
            # match multiple ways — distinct on the primary key is safe.
            rows_stmt = rows_stmt.distinct()
        rows = (await self._session.execute(rows_stmt)).scalars().all()
        return ProjectPage(
            items=[_to_entity(r) for r in rows],
            total=total,
            page=page,
            page_size=page_size,
        )

    async def get_by_id(self, project_id: UUID) -> Project | None:
        row = (
            await self._session.execute(select(ProjectModel).where(ProjectModel.id == project_id))
        ).scalar_one_or_none()
        return _to_entity(row) if row else None

    async def get_by_code(self, code: str) -> Project | None:
        row = (
            await self._session.execute(
                select(ProjectModel).where(func.lower(ProjectModel.code) == code.lower())
            )
        ).scalar_one_or_none()
        return _to_entity(row) if row else None

    async def save(self, project: Project) -> Project:
        row = ProjectModel(
            id=project.id,
            code=project.code,
            name=project.name,
            description=project.description,
            status=project.status,
            customer_id=project.customer_id,
            icon=project.icon,
            color=project.color,
            tags=list(project.tags),
            version=project.version,
            fecha_inicio=project.fecha_inicio,
            fecha_entrega_estimada=project.fecha_entrega_estimada,
            fecha_entrega_real=project.fecha_entrega_real,
            notas=project.notas,
        )
        self._session.add(row)
        try:
            await self._session.flush()
        except IntegrityError as exc:
            await self._session.rollback()
            if _is_code_unique_violation(exc):
                raise ProjectCodeAlreadyRegisteredError(
                    f"code already registered: {project.code}"
                ) from exc
            raise
        await self._session.commit()
        await self._session.refresh(row)
        return _to_entity(row)

    async def update(self, project: Project) -> Project:
        row = (
            await self._session.execute(select(ProjectModel).where(ProjectModel.id == project.id))
        ).scalar_one_or_none()
        if row is None:
            raise LookupError(f"project {project.id} disappeared mid-update")
        row.code = project.code
        row.name = project.name
        row.description = project.description
        row.status = project.status
        row.customer_id = project.customer_id
        row.icon = project.icon
        row.color = project.color
        row.tags = list(project.tags)
        row.version = project.version
        row.fecha_inicio = project.fecha_inicio
        row.fecha_entrega_estimada = project.fecha_entrega_estimada
        row.fecha_entrega_real = project.fecha_entrega_real
        row.notas = project.notas
        try:
            await self._session.flush()
        except IntegrityError as exc:
            await self._session.rollback()
            if _is_code_unique_violation(exc):
                raise ProjectCodeAlreadyRegisteredError(
                    f"code already registered: {project.code}"
                ) from exc
            raise
        await self._session.commit()
        await self._session.refresh(row)
        return _to_entity(row)

    async def soft_delete(self, project_id: UUID) -> bool:
        row = (
            await self._session.execute(select(ProjectModel).where(ProjectModel.id == project_id))
        ).scalar_one_or_none()
        if row is None:
            return False
        row.status = "Archivado"
        await self._session.flush()
        await self._session.commit()
        return True

    # ---------- children ----------

    async def list_children(self, parent_project_id: UUID) -> list[ProjectChild]:
        rows = (
            (
                await self._session.execute(
                    select(ProjectChildModel)
                    .where(ProjectChildModel.parent_project_id == parent_project_id)
                    .order_by(ProjectChildModel.sort_order, ProjectChildModel.created_at)
                )
            )
            .scalars()
            .all()
        )
        return [_child_to_entity(r) for r in rows]

    async def get_child(self, child_id: UUID) -> ProjectChild | None:
        row = (
            await self._session.execute(
                select(ProjectChildModel).where(ProjectChildModel.id == child_id)
            )
        ).scalar_one_or_none()
        return _child_to_entity(row) if row else None

    async def add_child(self, child: ProjectChild) -> ProjectChild:
        row = ProjectChildModel(
            id=child.id,
            parent_project_id=child.parent_project_id,
            child_module_id=child.child_module_id,
            child_component_id=child.child_component_id,
            quantity=child.quantity,
            sort_order=child.sort_order,
            notes=child.notes,
        )
        self._session.add(row)
        await self._session.flush()
        await self._session.commit()
        await self._session.refresh(row)
        return _child_to_entity(row)

    async def update_child(self, child: ProjectChild) -> ProjectChild:
        row = (
            await self._session.execute(
                select(ProjectChildModel).where(ProjectChildModel.id == child.id)
            )
        ).scalar_one_or_none()
        if row is None:
            raise LookupError(f"project_child {child.id} disappeared mid-update")
        row.quantity = child.quantity
        row.notes = child.notes
        row.sort_order = child.sort_order
        await self._session.flush()
        await self._session.commit()
        await self._session.refresh(row)
        return _child_to_entity(row)

    async def remove_child(self, child_id: UUID) -> bool:
        result = await self._session.execute(
            delete(ProjectChildModel).where(ProjectChildModel.id == child_id)
        )
        await self._session.commit()
        return (getattr(result, "rowcount", 0) or 0) > 0

    async def child_pair_exists(
        self,
        *,
        parent_project_id: UUID,
        child_module_id: UUID | None,
        child_component_id: UUID | None,
    ) -> bool:
        stmt = select(ProjectChildModel.id).where(
            ProjectChildModel.parent_project_id == parent_project_id,
        )
        if child_module_id is not None:
            stmt = stmt.where(ProjectChildModel.child_module_id == child_module_id)
        else:
            stmt = stmt.where(ProjectChildModel.child_component_id == child_component_id)
        return (await self._session.execute(stmt)).first() is not None

    # ---------- cross-feature "projects-using" ----------

    async def list_for_component(self, child_component_id: UUID) -> list[Project]:
        rows = (
            (
                await self._session.execute(
                    select(ProjectModel)
                    .join(
                        ProjectChildModel,
                        ProjectChildModel.parent_project_id == ProjectModel.id,
                    )
                    .where(ProjectChildModel.child_component_id == child_component_id)
                    .order_by(ProjectModel.name)
                )
            )
            .scalars()
            .all()
        )
        return [_to_entity(r) for r in rows]

    async def list_for_module(self, child_module_id: UUID) -> list[Project]:
        rows = (
            (
                await self._session.execute(
                    select(ProjectModel)
                    .join(
                        ProjectChildModel,
                        ProjectChildModel.parent_project_id == ProjectModel.id,
                    )
                    .where(ProjectChildModel.child_module_id == child_module_id)
                    .order_by(ProjectModel.name)
                )
            )
            .scalars()
            .all()
        )
        return [_to_entity(r) for r in rows]

    # ---------- aggregate primitives ----------

    async def list_descendant_components(
        self,
        project_id: UUID,
    ) -> list[tuple[UUID, int]]:
        """Flatten every component leaf reachable from a project.

        Walks `project_children` for direct edges, then descends through
        `module_children` for any module hijos. Depth-bounded to 8 like the
        modules path. Returns `(component_id, propagated_qty)` tuples;
        components reached via multiple paths appear multiple times — caller
        sums them.
        """
        sql = text(
            """
            WITH RECURSIVE walk(level, child_module_id, child_component_id, qty, depth) AS (
                -- Direct project edges (level 0)
                SELECT 0::int AS level,
                       pc.child_module_id,
                       pc.child_component_id,
                       pc.quantity::int AS qty,
                       1 AS depth
                FROM project_children pc
                WHERE pc.parent_project_id = :root
                UNION ALL
                -- Descend through module_children (level 1+)
                SELECT 1::int AS level,
                       mc.child_module_id,
                       mc.child_component_id,
                       (w.qty * mc.quantity)::int,
                       w.depth + 1
                FROM module_children mc
                JOIN walk w ON mc.parent_module_id = w.child_module_id
                WHERE w.child_module_id IS NOT NULL AND w.depth < 8
            )
            SELECT child_component_id, qty
            FROM walk
            WHERE child_component_id IS NOT NULL
            """
        )
        rows = (await self._session.execute(sql, {"root": project_id})).all()
        return [(cast(UUID, r[0]), int(r[1])) for r in rows]

    async def list_descendant_modules(
        self,
        project_id: UUID,
    ) -> list[tuple[UUID, int]]:
        """Flatten module nodes reachable from a project (used by buildable_stock).

        Returns `(module_id, propagated_qty)` tuples for every module reached
        through the BOM, with cumulative quantity along the path.
        """
        sql = text(
            """
            WITH RECURSIVE walk(child_module_id, qty, depth) AS (
                SELECT pc.child_module_id, pc.quantity::int, 1
                FROM project_children pc
                WHERE pc.parent_project_id = :root
                  AND pc.child_module_id IS NOT NULL
                UNION ALL
                SELECT mc.child_module_id, (w.qty * mc.quantity)::int, w.depth + 1
                FROM module_children mc
                JOIN walk w ON mc.parent_module_id = w.child_module_id
                WHERE mc.child_module_id IS NOT NULL AND w.depth < 8
            )
            SELECT child_module_id, qty FROM walk
            """
        )
        rows = (await self._session.execute(sql, {"root": project_id})).all()
        return [(cast(UUID, r[0]), int(r[1])) for r in rows]

    async def list_price_history(
        self,
        *,
        project_id: UUID,
        period: PeriodLiteral,
    ) -> list[ProjectPriceHistoryPoint]:
        """Aggregated price series — same algorithm as `ModuleService.list_price_history`."""
        cutoff = _period_cutoff(period)
        descendants = await self.list_descendant_components(project_id)
        if not descendants:
            return []

        qty_by_comp: dict[UUID, int] = {}
        for comp_id, qty in descendants:
            qty_by_comp[comp_id] = qty_by_comp.get(comp_id, 0) + qty
        comp_ids = list(qty_by_comp.keys())

        prefs = (
            await self._session.execute(
                select(ComponentModel.id, ComponentModel.proveedor_preferente_id).where(
                    ComponentModel.id.in_(comp_ids)
                )
            )
        ).all()
        pref_by_comp: dict[UUID, UUID | None] = {
            cast(UUID, r[0]): cast(UUID | None, r[1]) for r in prefs
        }

        pairs = [(comp_id, pref) for comp_id, pref in pref_by_comp.items() if pref is not None]
        if not pairs:
            return []

        rows = (
            await self._session.execute(
                select(
                    SupplierPriceModel.component_id,
                    SupplierPriceModel.supplier_id,
                    SupplierPriceModel.price,
                    SupplierPriceModel.valid_from,
                )
                .where(SupplierPriceModel.qty_tier == 100)
                .where(SupplierPriceModel.valid_from >= cutoff)
                .where(SupplierPriceModel.component_id.in_([p[0] for p in pairs]))
                .order_by(SupplierPriceModel.valid_from)
            )
        ).all()

        by_pair: dict[tuple[UUID, UUID], list[tuple[date, Decimal]]] = {}
        for r in rows:
            comp_id, sup_id = cast(UUID, r[0]), cast(UUID, r[1])
            if pref_by_comp.get(comp_id) != sup_id:
                continue
            key = (comp_id, sup_id)
            by_pair.setdefault(key, []).append((cast(date, r[3]), cast(Decimal, r[2])))

        all_dates = sorted({d for series in by_pair.values() for (d, _) in series})
        if not all_dates:
            return []

        out: list[ProjectPriceHistoryPoint] = []
        for d in all_dates:
            total = Decimal("0")
            for (comp_id, _sup), series in by_pair.items():
                latest: Decimal | None = None
                for vf, price in series:
                    if vf <= d:
                        latest = price
                    else:
                        break
                if latest is None:
                    continue
                total += latest * qty_by_comp[comp_id]
            out.append(ProjectPriceHistoryPoint(date=d, price=total))
        return out
