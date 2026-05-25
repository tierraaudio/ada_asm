"""SQLAlchemy-backed implementation of `ModuleRepository`.

Covers persistence + the DB-level cycle-detection query via WITH RECURSIVE.
Aggregate computation (price totals, MIN scoring, buildable stock) lives in
`ModuleService` — the repo only flattens the descendant components tree.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import cast
from uuid import UUID

from sqlalchemy import delete, func, or_, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ModuleSkuAlreadyRegisteredError
from app.domain.entities.module import Module, ModuleFamilyValue
from app.domain.entities.module_child import ModuleChild
from app.domain.repositories.module_repository import (
    ModuleFilters,
    ModulePage,
    ModulePriceHistoryPoint,
    PeriodLiteral,
)
from app.infrastructure.db.models.component import ComponentModel
from app.infrastructure.db.models.module import ModuleModel
from app.infrastructure.db.models.module_child import ModuleChildModel
from app.infrastructure.db.models.supplier_price import SupplierPriceModel


def _to_entity(row: ModuleModel) -> Module:
    return Module(
        id=row.id,
        sku=row.sku,
        name=row.name,
        description=row.description,
        version=row.version,
        family=cast(ModuleFamilyValue, row.family),
        fabricante=row.fabricante,
        location=row.location,
        tipo_almacenamiento=row.tipo_almacenamiento,
        stock=row.stock,
        notas=row.notas,
        fecha_creacion=row.fecha_creacion,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _child_to_entity(row: ModuleChildModel) -> ModuleChild:
    return ModuleChild(
        id=row.id,
        parent_module_id=row.parent_module_id,
        child_module_id=row.child_module_id,
        child_component_id=row.child_component_id,
        quantity=row.quantity,
        sort_order=row.sort_order,
        notes=row.notes,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _is_sku_unique_violation(exc: IntegrityError) -> bool:
    msg = str(exc.orig).lower()
    return "uq_modules_sku_lower" in msg


def _period_cutoff(period: PeriodLiteral) -> date:
    today = date.today()
    if period == "week":
        return today - timedelta(days=7)
    if period == "month":
        return today - timedelta(days=30)
    return today - timedelta(days=365)


class SqlAlchemyModuleRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ---------- modules ----------

    async def list_modules(
        self,
        *,
        filters: ModuleFilters,
        page: int,
        page_size: int,
    ) -> ModulePage:
        stmt = select(ModuleModel)
        if filters.q is not None and filters.q.strip():
            needle = f"%{filters.q.strip().lower()}%"
            stmt = stmt.where(
                or_(
                    func.lower(ModuleModel.sku).like(needle),
                    func.lower(ModuleModel.name).like(needle),
                    func.lower(ModuleModel.description).like(needle),
                )
            )
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await self._session.execute(count_stmt)).scalar_one()
        rows = (
            (
                await self._session.execute(
                    stmt.order_by(ModuleModel.created_at.desc())
                    .limit(page_size)
                    .offset((page - 1) * page_size)
                )
            )
            .scalars()
            .all()
        )
        return ModulePage(
            items=[_to_entity(r) for r in rows],
            total=total,
            page=page,
            page_size=page_size,
        )

    async def get_by_id(self, module_id: UUID) -> Module | None:
        row = (
            await self._session.execute(select(ModuleModel).where(ModuleModel.id == module_id))
        ).scalar_one_or_none()
        return _to_entity(row) if row else None

    async def get_by_sku(self, sku: str) -> Module | None:
        row = (
            await self._session.execute(
                select(ModuleModel).where(func.lower(ModuleModel.sku) == sku.lower())
            )
        ).scalar_one_or_none()
        return _to_entity(row) if row else None

    async def save(self, module: Module) -> Module:
        row = ModuleModel(
            id=module.id,
            sku=module.sku,
            name=module.name,
            description=module.description,
            version=module.version,
            family=module.family,
            fabricante=module.fabricante,
            location=module.location,
            tipo_almacenamiento=module.tipo_almacenamiento,
            stock=module.stock,
            notas=module.notas,
            fecha_creacion=module.fecha_creacion,
        )
        self._session.add(row)
        try:
            await self._session.flush()
        except IntegrityError as exc:
            await self._session.rollback()
            if _is_sku_unique_violation(exc):
                raise ModuleSkuAlreadyRegisteredError(
                    f"sku already registered: {module.sku}"
                ) from exc
            raise
        await self._session.commit()
        await self._session.refresh(row)
        return _to_entity(row)

    async def update(self, module: Module) -> Module:
        row = (
            await self._session.execute(select(ModuleModel).where(ModuleModel.id == module.id))
        ).scalar_one_or_none()
        if row is None:
            raise LookupError(f"module {module.id} disappeared mid-update")
        row.sku = module.sku
        row.name = module.name
        row.description = module.description
        row.version = module.version
        row.family = module.family
        row.fabricante = module.fabricante
        row.location = module.location
        row.tipo_almacenamiento = module.tipo_almacenamiento
        row.stock = module.stock
        row.notas = module.notas
        row.fecha_creacion = module.fecha_creacion
        try:
            await self._session.flush()
        except IntegrityError as exc:
            await self._session.rollback()
            if _is_sku_unique_violation(exc):
                raise ModuleSkuAlreadyRegisteredError(
                    f"sku already registered: {module.sku}"
                ) from exc
            raise
        await self._session.commit()
        await self._session.refresh(row)
        return _to_entity(row)

    async def delete(self, module_id: UUID) -> bool:
        result = await self._session.execute(delete(ModuleModel).where(ModuleModel.id == module_id))
        await self._session.commit()
        return (getattr(result, "rowcount", 0) or 0) > 0

    # ---------- children ----------

    async def list_children(self, parent_module_id: UUID) -> list[ModuleChild]:
        rows = (
            (
                await self._session.execute(
                    select(ModuleChildModel)
                    .where(ModuleChildModel.parent_module_id == parent_module_id)
                    .order_by(ModuleChildModel.sort_order, ModuleChildModel.created_at)
                )
            )
            .scalars()
            .all()
        )
        return [_child_to_entity(r) for r in rows]

    async def list_parents(self, child_module_id: UUID) -> list[Module]:
        rows = (
            (
                await self._session.execute(
                    select(ModuleModel)
                    .join(
                        ModuleChildModel,
                        ModuleChildModel.parent_module_id == ModuleModel.id,
                    )
                    .where(ModuleChildModel.child_module_id == child_module_id)
                    .order_by(ModuleModel.name)
                )
            )
            .scalars()
            .all()
        )
        return [_to_entity(r) for r in rows]

    async def get_child(self, child_id: UUID) -> ModuleChild | None:
        row = (
            await self._session.execute(
                select(ModuleChildModel).where(ModuleChildModel.id == child_id)
            )
        ).scalar_one_or_none()
        return _child_to_entity(row) if row else None

    async def add_child(self, child: ModuleChild) -> ModuleChild:
        row = ModuleChildModel(
            id=child.id,
            parent_module_id=child.parent_module_id,
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

    async def update_child(self, child: ModuleChild) -> ModuleChild:
        row = (
            await self._session.execute(
                select(ModuleChildModel).where(ModuleChildModel.id == child.id)
            )
        ).scalar_one_or_none()
        if row is None:
            raise LookupError(f"module_child {child.id} disappeared mid-update")
        row.quantity = child.quantity
        row.notes = child.notes
        row.sort_order = child.sort_order
        await self._session.flush()
        await self._session.commit()
        await self._session.refresh(row)
        return _child_to_entity(row)

    async def remove_child(self, child_id: UUID) -> bool:
        result = await self._session.execute(
            delete(ModuleChildModel).where(ModuleChildModel.id == child_id)
        )
        await self._session.commit()
        return (getattr(result, "rowcount", 0) or 0) > 0

    async def child_pair_exists(
        self,
        *,
        parent_module_id: UUID,
        child_module_id: UUID | None,
        child_component_id: UUID | None,
    ) -> bool:
        stmt = select(ModuleChildModel.id).where(
            ModuleChildModel.parent_module_id == parent_module_id,
        )
        if child_module_id is not None:
            stmt = stmt.where(ModuleChildModel.child_module_id == child_module_id)
        else:
            stmt = stmt.where(ModuleChildModel.child_component_id == child_component_id)
        return (await self._session.execute(stmt)).first() is not None

    async def check_cycle(
        self,
        *,
        parent_module_id: UUID,
        candidate_child_module_id: UUID,
    ) -> bool:
        if parent_module_id == candidate_child_module_id:
            return True
        result = await self._session.execute(
            text(
                """
                WITH RECURSIVE descendants(id) AS (
                    SELECT child_module_id FROM module_children
                        WHERE parent_module_id = :child
                          AND child_module_id IS NOT NULL
                    UNION ALL
                    SELECT mc.child_module_id FROM module_children mc
                        JOIN descendants d ON mc.parent_module_id = d.id
                        WHERE mc.child_module_id IS NOT NULL
                )
                SELECT 1 FROM descendants WHERE id = :parent LIMIT 1
                """
            ),
            {"child": candidate_child_module_id, "parent": parent_module_id},
        )
        return result.first() is not None

    # ---------- aggregate primitives ----------

    async def list_descendant_components(
        self,
        module_id: UUID,
    ) -> list[tuple[UUID, int]]:
        """Recursively flatten leaves under `module_id`.

        Walks the DAG depth-bounded to 8 to prevent runaway, multiplying
        quantities along the path. Returns `(component_id, propagated_qty)`.
        Components may appear multiple times if reached via different paths;
        callers sum them as needed.
        """
        sql = text(
            """
            WITH RECURSIVE walk(parent_id, child_module_id, child_component_id, qty, depth) AS (
                SELECT mc.parent_module_id, mc.child_module_id, mc.child_component_id,
                       mc.quantity::int, 1
                FROM module_children mc
                WHERE mc.parent_module_id = :root
                UNION ALL
                SELECT mc.parent_module_id, mc.child_module_id, mc.child_component_id,
                       (w.qty * mc.quantity)::int, w.depth + 1
                FROM module_children mc
                JOIN walk w ON mc.parent_module_id = w.child_module_id
                WHERE w.child_module_id IS NOT NULL AND w.depth < 8
            )
            SELECT child_component_id, qty
            FROM walk
            WHERE child_component_id IS NOT NULL
            """
        )
        rows = (await self._session.execute(sql, {"root": module_id})).all()
        return [(cast(UUID, r[0]), int(r[1])) for r in rows]

    async def list_descendant_modules(
        self,
        module_id: UUID,
    ) -> list[tuple[UUID, int]]:
        """Recursively flatten *child modules* (used by buildable_stock)."""
        sql = text(
            """
            WITH RECURSIVE walk(parent_id, child_module_id, qty, depth) AS (
                SELECT mc.parent_module_id, mc.child_module_id, mc.quantity::int, 1
                FROM module_children mc
                WHERE mc.parent_module_id = :root
                  AND mc.child_module_id IS NOT NULL
                UNION ALL
                SELECT mc.parent_module_id, mc.child_module_id,
                       (w.qty * mc.quantity)::int, w.depth + 1
                FROM module_children mc
                JOIN walk w ON mc.parent_module_id = w.child_module_id
                WHERE mc.child_module_id IS NOT NULL AND w.depth < 8
            )
            SELECT child_module_id, qty FROM walk
            """
        )
        rows = (await self._session.execute(sql, {"root": module_id})).all()
        return [(cast(UUID, r[0]), int(r[1])) for r in rows]

    async def list_price_history(
        self,
        *,
        module_id: UUID,
        period: PeriodLiteral,
    ) -> list[ModulePriceHistoryPoint]:
        """Aggregated price series, ready to plot.

        For each `valid_from` date in the period, sums
        `quantity_propagada x precio_vigente_a_esa_fecha` over every
        descendant component, using each component's preferred supplier at
        `qty_tier=100`.
        """
        cutoff = _period_cutoff(period)
        descendants = await self.list_descendant_components(module_id)
        if not descendants:
            return []

        # Sum propagated qty per component (in case the same component is
        # reached via multiple paths).
        qty_by_comp: dict[UUID, int] = {}
        for comp_id, qty in descendants:
            qty_by_comp[comp_id] = qty_by_comp.get(comp_id, 0) + qty
        comp_ids = list(qty_by_comp.keys())

        # Pull each component's preferred supplier id.
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

        # Pull all relevant supplier_prices for those (component, preferred-supplier)
        # pairs at qty_tier=100 within the period.
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

        # Group rows by (component, supplier) → list of (date, price).
        by_pair: dict[tuple[UUID, UUID], list[tuple[date, Decimal]]] = {}
        for r in rows:
            comp_id, sup_id = cast(UUID, r[0]), cast(UUID, r[1])
            if pref_by_comp.get(comp_id) != sup_id:
                continue  # not the preferred supplier for this component
            key = (comp_id, sup_id)
            by_pair.setdefault(key, []).append((cast(date, r[3]), cast(Decimal, r[2])))

        # Collect the union of dates we'll plot.
        all_dates = sorted({d for series in by_pair.values() for (d, _) in series})
        if not all_dates:
            return []

        # For each date, sum across components using the latest known price
        # for each component on/before that date.
        out: list[ModulePriceHistoryPoint] = []
        for d in all_dates:
            total = Decimal("0")
            for (comp_id, _sup), series in by_pair.items():
                # latest price with valid_from <= d
                latest: Decimal | None = None
                for vf, price in series:
                    if vf <= d:
                        latest = price
                    else:
                        break
                if latest is None:
                    continue
                total += latest * qty_by_comp[comp_id]
            out.append(ModulePriceHistoryPoint(date=d, price=total))
        return out
