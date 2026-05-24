"""Module catalogue + DAG service.

Orchestrates between API and persistence. Owns:

- CRUD on modules with `ModuleNotFoundError` / `ModuleSkuAlreadyRegisteredError`.
- Child-edge CRUD with XOR + cycle + duplicate validation.
- On-the-fly aggregate computation (price total, MIN scoring/tier, MIN
  expires_at, buildable stock) for the detail endpoint.
- Aggregate price history (delegates to the repo's recursive query).
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

from app.core.exceptions import (
    ChildAlreadyPresentError,
    InvalidChildReferenceError,
    ModuleCycleDetectedError,
    ModuleNotFoundError,
)
from app.domain.entities.component import NatoScoreValue, TierValue
from app.domain.entities.module import Module, ModuleAggregates
from app.domain.entities.module_child import ModuleChild
from app.domain.repositories.module_repository import (
    ModuleFilters,
    ModulePage,
    ModulePriceHistoryPoint,
    PeriodLiteral,
)
from app.infrastructure.db.models.component import ComponentModel
from app.infrastructure.db.models.nato_scoring import ComponentNatoScoringModel
from app.infrastructure.repositories.module_repository import SqlAlchemyModuleRepository

logger = structlog.get_logger(__name__)

# Lex order from worst to best. Index = "worse-ness rank".
NATO_ORDER: list[NatoScoreValue] = ["F", "D", "C", "B", "A", "A+"]


def _worst_nato_score(scores: list[NatoScoreValue]) -> NatoScoreValue | None:
    """MIN in lex order F < D < C < B < A < A+ (F is worst)."""
    if not scores:
        return None
    ranks: dict[str, int] = {s: i for i, s in enumerate(NATO_ORDER)}
    best_rank = len(NATO_ORDER)
    worst: NatoScoreValue = scores[0]
    for s in scores:
        r = ranks[cast(str, s)]
        if r < best_rank:
            best_rank = r
            worst = s
    return worst


@dataclass
class ModuleCreate:
    sku: str
    name: str
    description: str | None = None
    version: str = "v1.0"
    fabricante: str | None = None
    location: str | None = None
    tipo_almacenamiento: str | None = None
    stock: int = 0
    notas: str | None = None
    fecha_creacion: date | None = None


@dataclass
class ModuleUpdate:
    """All fields optional — missing means 'leave alone'."""

    sku: str | None = None
    name: str | None = None
    description: str | None = None
    version: str | None = None
    fabricante: str | None = None
    location: str | None = None
    tipo_almacenamiento: str | None = None
    stock: int | None = None
    notas: str | None = None
    fecha_creacion: date | None = None
    # Sentinel-aware fields: callers signal "set to NULL" by passing the
    # explicit None; "leave unchanged" by omitting the key entirely. The
    # router routes its payload through `_apply_update`.


@dataclass
class AddChildInput:
    child_module_id: UUID | None = None
    child_component_id: UUID | None = None
    quantity: int = 1
    notes: str | None = None
    sort_order: int = 0


@dataclass
class UpdateChildInput:
    quantity: int | None = None
    notes: str | None = None
    sort_order: int | None = None


@dataclass
class ModuleDetailBundle:
    module: Module
    aggregates: ModuleAggregates
    children: list[ModuleChild]
    parents: list[Module]


@dataclass
class _ComponentRollup:
    """Component fields needed to compute aggregates for a module subtree."""

    id: UUID
    stock: int
    nato_score: NatoScoreValue
    tier: TierValue
    expires_at: date | None = None
    # Cached so the price endpoint doesn't need its own walk.
    name: str = ""
    mpn: str = ""


class ModuleService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = SqlAlchemyModuleRepository(session)

    # ---------- CRUD ----------

    async def list_modules(
        self, *, filters: ModuleFilters, page: int, page_size: int
    ) -> ModulePage:
        return await self._repo.list_modules(filters=filters, page=page, page_size=page_size)

    async def get(self, module_id: UUID) -> Module:
        m = await self._repo.get_by_id(module_id)
        if m is None:
            raise ModuleNotFoundError(f"module not found: {module_id}")
        return m

    async def get_detail(self, module_id: UUID) -> ModuleDetailBundle:
        module = await self.get(module_id)
        children = await self._repo.list_children(module_id)
        parents = await self._repo.list_parents(module_id)
        aggregates = await self.compute_aggregates(module_id, module_stock=module.stock)
        return ModuleDetailBundle(
            module=module,
            aggregates=aggregates,
            children=children,
            parents=parents,
        )

    async def create(self, payload: ModuleCreate) -> Module:
        module = Module(
            sku=payload.sku,
            name=payload.name,
            description=payload.description,
            version=payload.version,
            fabricante=payload.fabricante,
            location=payload.location,
            tipo_almacenamiento=payload.tipo_almacenamiento,
            stock=payload.stock,
            notas=payload.notas,
            fecha_creacion=payload.fecha_creacion,
        )
        saved = await self._repo.save(module)
        logger.info("module.created", module_id=str(saved.id), sku=saved.sku)
        return saved

    async def update(self, module_id: UUID, patch: ModuleUpdate) -> Module:
        current = await self.get(module_id)
        if patch.sku is not None:
            current.sku = patch.sku
        if patch.name is not None:
            current.name = patch.name
        if patch.description is not None:
            current.description = patch.description
        if patch.version is not None:
            current.version = patch.version
        if patch.fabricante is not None:
            current.fabricante = patch.fabricante
        if patch.location is not None:
            current.location = patch.location
        if patch.tipo_almacenamiento is not None:
            current.tipo_almacenamiento = patch.tipo_almacenamiento
        if patch.stock is not None:
            current.stock = patch.stock
        if patch.notas is not None:
            current.notas = patch.notas
        if patch.fecha_creacion is not None:
            current.fecha_creacion = patch.fecha_creacion
        return await self._repo.update(current)

    async def delete(self, module_id: UUID) -> None:
        if not await self._repo.delete(module_id):
            raise ModuleNotFoundError(f"module not found: {module_id}")

    # ---------- children ----------

    async def add_child(self, parent_module_id: UUID, payload: AddChildInput) -> ModuleChild:
        await self.get(parent_module_id)  # 404 if missing

        if (payload.child_module_id is None) == (payload.child_component_id is None):
            raise InvalidChildReferenceError(
                "exactly one of child_module_id / child_component_id must be set"
            )

        if payload.quantity < 1:
            raise InvalidChildReferenceError("quantity must be >= 1")

        # Verify referenced row exists (so the 422 surfaces here, not as a FK
        # error from the DB).
        if payload.child_module_id is not None:
            child = await self._repo.get_by_id(payload.child_module_id)
            if child is None:
                raise InvalidChildReferenceError(
                    f"child module not found: {payload.child_module_id}"
                )
            if await self._repo.check_cycle(
                parent_module_id=parent_module_id,
                candidate_child_module_id=payload.child_module_id,
            ):
                raise ModuleCycleDetectedError(
                    "adding this child would close a cycle in the module graph"
                )
        else:
            assert payload.child_component_id is not None  # narrows for mypy
            comp = (
                await self._session.execute(
                    select(ComponentModel.id).where(ComponentModel.id == payload.child_component_id)
                )
            ).scalar_one_or_none()
            if comp is None:
                raise InvalidChildReferenceError(
                    f"child component not found: {payload.child_component_id}"
                )

        if await self._repo.child_pair_exists(
            parent_module_id=parent_module_id,
            child_module_id=payload.child_module_id,
            child_component_id=payload.child_component_id,
        ):
            raise ChildAlreadyPresentError(
                "this child is already present — update quantity instead"
            )

        return await self._repo.add_child(
            ModuleChild(
                parent_module_id=parent_module_id,
                child_module_id=payload.child_module_id,
                child_component_id=payload.child_component_id,
                quantity=payload.quantity,
                notes=payload.notes,
                sort_order=payload.sort_order,
            )
        )

    async def update_child(
        self, parent_module_id: UUID, child_id: UUID, patch: UpdateChildInput
    ) -> ModuleChild:
        await self.get(parent_module_id)
        existing = await self._repo.get_child(child_id)
        if existing is None or existing.parent_module_id != parent_module_id:
            raise ModuleNotFoundError(
                f"module_child not found: {child_id} (in module {parent_module_id})"
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

    async def remove_child(self, parent_module_id: UUID, child_id: UUID) -> None:
        # Idempotent on missing — matches the components delete contract.
        existing = await self._repo.get_child(child_id)
        if existing is None or existing.parent_module_id != parent_module_id:
            return
        await self._repo.remove_child(child_id)

    # ---------- aggregates ----------

    async def _collect_component_rollups(
        self, module_id: UUID
    ) -> list[tuple[_ComponentRollup, int]]:
        """For every descendant leaf, return its rollup + propagated quantity."""
        descendants = await self._repo.list_descendant_components(module_id)
        if not descendants:
            return []
        # Sum propagated qty per component (same component can appear twice
        # via different paths).
        qty_by_comp: dict[UUID, int] = {}
        for cid, q in descendants:
            qty_by_comp[cid] = qty_by_comp.get(cid, 0) + q

        comp_rows = (
            await self._session.execute(
                select(
                    ComponentModel.id,
                    ComponentModel.stock,
                    ComponentModel.nato_score,
                    ComponentModel.tier,
                    ComponentModel.name,
                    ComponentModel.mpn,
                ).where(ComponentModel.id.in_(qty_by_comp.keys()))
            )
        ).all()

        # Latest 100u price per component from preferred supplier — used by
        # the price aggregate.
        from app.infrastructure.db.models.supplier_price import SupplierPriceModel

        comp_ids = list(qty_by_comp.keys())
        pref_rows = (
            await self._session.execute(
                select(ComponentModel.id, ComponentModel.proveedor_preferente_id).where(
                    ComponentModel.id.in_(comp_ids)
                )
            )
        ).all()
        pref_by_comp: dict[UUID, UUID | None] = {
            cast(UUID, r[0]): cast(UUID | None, r[1]) for r in pref_rows
        }

        # Active scoring expires_at per component.
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

        # Latest qty_tier=100 price per (component, preferred-supplier).
        self._price_cache: dict[UUID, Decimal] = {}
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
                self._price_cache[comp_id] = row

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
                        name=cast(str, r[4]),
                        mpn=cast(str, r[5]),
                    ),
                    qty_by_comp[cid],
                )
            )
        return rollups

    async def compute_aggregates(self, module_id: UUID, *, module_stock: int) -> ModuleAggregates:
        rollups = await self._collect_component_rollups(module_id)
        if not rollups:
            return ModuleAggregates(buildable_stock=0)

        # Price total: sum( qty x current_price ).
        total = Decimal("0")
        prices = getattr(self, "_price_cache", {})
        for comp, qty in rollups:
            price = prices.get(comp.id)
            if price is not None:
                total += price * qty

        # Worst NATO + worst tier among descendants.
        scores = [c.nato_score for c, _ in rollups]
        worst_score = _worst_nato_score(scores)
        worst_tier = min(c.tier for c, _ in rollups)

        # MIN expires_at (null-safe).
        valid_expiries = [c.expires_at for c, _ in rollups if c.expires_at is not None]
        worst_expiry = min(valid_expiries) if valid_expiries else None

        # Buildable stock: for each *direct* child, compute how many wholes
        # we can build given that child's stock; take the min.
        direct = await self._repo.list_children(module_id)
        buildable = self._compute_buildable(direct, rollups, module_stock)

        return ModuleAggregates(
            precio_total=total if total > 0 else None,
            aggregated_nato_score=worst_score,
            aggregated_tier=worst_tier,
            aggregated_expires_at=worst_expiry,
            buildable_stock=buildable,
        )

    def _compute_buildable(
        self,
        direct_children: list[ModuleChild],
        all_rollups: list[tuple[_ComponentRollup, int]],
        module_stock: int,
    ) -> int:
        """Min over direct *component* children of `child.stock // edge.quantity`.

        Submodule children are ignored in this metric — counting them properly
        would require recursive buildable computation per subtree, which is
        out of scope for this iteration. The FE tooltip surfaces this caveat.
        """
        _ = module_stock  # not used in this metric; kept on signature for clarity
        component_edges = [e for e in direct_children if e.child_component_id is not None]
        if not component_edges:
            return 0
        per_component_stock = {c.id: c.stock for c, _ in all_rollups}
        capacities: list[int] = []
        for edge in component_edges:
            assert edge.child_component_id is not None
            stock = per_component_stock.get(edge.child_component_id, 0)
            capacities.append(stock // max(edge.quantity, 1))
        return min(capacities) if capacities else 0

    async def list_price_history(
        self, module_id: UUID, *, period: PeriodLiteral
    ) -> list[ModulePriceHistoryPoint]:
        await self.get(module_id)
        return await self._repo.list_price_history(module_id=module_id, period=period)
