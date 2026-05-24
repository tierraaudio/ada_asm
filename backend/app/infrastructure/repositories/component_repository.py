"""SQLAlchemy-backed implementation of `ComponentRepository`."""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal
from typing import cast
from uuid import UUID

from sqlalchemy import delete, func, or_, select, tuple_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ComponentMpnAlreadyRegisteredError
from app.domain.entities.component import Component, NatoScoreValue, TierValue
from app.domain.repositories.component_repository import (
    ComponentFilters,
    ComponentPage,
)
from app.infrastructure.db.models.component import ComponentModel
from app.infrastructure.db.models.supplier_price import SupplierPriceModel


def _to_entity(row: ComponentModel) -> Component:
    return Component(
        id=row.id,
        mpn=row.mpn,
        sku=row.sku,
        name=row.name,
        family=row.family,
        description=row.description,
        datasheet_url=row.datasheet_url,
        location=row.location,
        fabricante=row.fabricante,
        tipo_almacenamiento=row.tipo_almacenamiento,
        holded_id=row.holded_id,
        fecha_creacion=row.fecha_creacion,
        notas=row.notas,
        stock=row.stock,
        stock_min=row.stock_min,
        tier=cast(TierValue, row.tier),
        nato_score=cast(NatoScoreValue, row.nato_score),
        country_of_origin=row.country_of_origin,
        proveedor_preferente_id=row.proveedor_preferente_id,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _is_mpn_unique_violation(exc: IntegrityError) -> bool:
    msg = str(exc.orig).lower()
    return "uq_components_mpn_lower" in msg or "components_mpn" in msg


class SqlAlchemyComponentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list(
        self,
        *,
        filters: ComponentFilters,
        page: int,
        page_size: int,
    ) -> ComponentPage:
        stmt = select(ComponentModel)

        if filters.families:
            stmt = stmt.where(ComponentModel.family.in_(filters.families))
        if filters.supplier_ids:
            stmt = stmt.where(ComponentModel.proveedor_preferente_id.in_(filters.supplier_ids))
        if filters.tiers:
            stmt = stmt.where(ComponentModel.tier.in_(filters.tiers))
        if filters.nato_scores:
            stmt = stmt.where(ComponentModel.nato_score.in_(filters.nato_scores))
        if filters.locations:
            stmt = stmt.where(ComponentModel.location.in_(filters.locations))
        if filters.q is not None and filters.q.strip():
            needle = f"%{filters.q.strip().lower()}%"
            stmt = stmt.where(
                or_(
                    func.lower(ComponentModel.mpn).like(needle),
                    func.lower(ComponentModel.sku).like(needle),
                    func.lower(ComponentModel.name).like(needle),
                    func.lower(ComponentModel.family).like(needle),
                )
            )

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = int((await self._session.execute(count_stmt)).scalar_one())

        offset = (page - 1) * page_size
        stmt = stmt.order_by(ComponentModel.name.asc()).limit(page_size).offset(offset)
        result = await self._session.execute(stmt)
        items = [_to_entity(row) for row in result.scalars().all()]

        # Hydrate `current_price_per_100_eur` for the page: 1 extra query that
        # picks the latest `valid_from` price per (component, preferred supplier)
        # where qty_tier=100. Items without a preferred supplier stay at None.
        await self._hydrate_current_prices(items)

        return ComponentPage(items=items, total=total, page=page, page_size=page_size)

    async def _hydrate_current_prices(self, items: Sequence[Component]) -> None:
        pairs = [
            (c.id, c.proveedor_preferente_id)
            for c in items
            if c.proveedor_preferente_id is not None
        ]
        if not pairs:
            return

        # Window function: rank rows per (component, supplier) by valid_from DESC,
        # then keep rank=1. Filters to qty_tier=100 + the pairs we care about.
        ranked = (
            select(
                SupplierPriceModel.component_id,
                SupplierPriceModel.supplier_id,
                SupplierPriceModel.price,
                func.row_number()
                .over(
                    partition_by=(
                        SupplierPriceModel.component_id,
                        SupplierPriceModel.supplier_id,
                    ),
                    order_by=SupplierPriceModel.valid_from.desc(),
                )
                .label("rn"),
            )
            .where(SupplierPriceModel.qty_tier == 100)
            .where(
                tuple_(
                    SupplierPriceModel.component_id,
                    SupplierPriceModel.supplier_id,
                ).in_(pairs)
            )
            .subquery()
        )
        stmt = select(ranked.c.component_id, ranked.c.price).where(ranked.c.rn == 1)
        result = await self._session.execute(stmt)
        price_by_component: dict[UUID, Decimal] = {
            row.component_id: row.price for row in result.all()
        }
        for item in items:
            item.current_price_per_100_eur = price_by_component.get(item.id)

    async def get_by_id(self, component_id: UUID) -> Component | None:
        row = await self._session.get(ComponentModel, component_id)
        return _to_entity(row) if row else None

    async def get_by_mpn(self, mpn: str) -> Component | None:
        stmt = select(ComponentModel).where(func.lower(ComponentModel.mpn) == mpn.lower())
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return _to_entity(row) if row else None

    async def save(self, component: Component) -> Component:
        row = ComponentModel(
            id=component.id,
            mpn=component.mpn,
            sku=component.sku,
            name=component.name,
            family=component.family,
            description=component.description,
            datasheet_url=component.datasheet_url,
            location=component.location,
            fabricante=component.fabricante,
            tipo_almacenamiento=component.tipo_almacenamiento,
            holded_id=component.holded_id,
            fecha_creacion=component.fecha_creacion,
            notas=component.notas,
            stock=component.stock,
            stock_min=component.stock_min,
            tier=component.tier,
            nato_score=component.nato_score,
            country_of_origin=component.country_of_origin,
            proveedor_preferente_id=component.proveedor_preferente_id,
        )
        self._session.add(row)
        try:
            await self._session.flush()
        except IntegrityError as exc:
            await self._session.rollback()
            if _is_mpn_unique_violation(exc):
                raise ComponentMpnAlreadyRegisteredError(
                    f"MPN '{component.mpn}' is already registered"
                ) from exc
            raise
        await self._session.refresh(row)
        return _to_entity(row)

    async def update(self, component: Component) -> Component:
        row = await self._session.get(ComponentModel, component.id)
        if row is None:
            return component
        # `mpn` is intentionally NOT copied — it is immutable in this US.
        row.sku = component.sku
        row.name = component.name
        row.family = component.family
        row.description = component.description
        row.datasheet_url = component.datasheet_url
        row.location = component.location
        row.fabricante = component.fabricante
        row.tipo_almacenamiento = component.tipo_almacenamiento
        row.holded_id = component.holded_id
        row.fecha_creacion = component.fecha_creacion
        row.notas = component.notas
        row.stock = component.stock
        row.stock_min = component.stock_min
        row.tier = component.tier
        row.nato_score = component.nato_score
        row.country_of_origin = component.country_of_origin
        row.proveedor_preferente_id = component.proveedor_preferente_id
        await self._session.flush()
        await self._session.refresh(row)
        return _to_entity(row)

    async def delete(self, component_id: UUID) -> bool:
        stmt = delete(ComponentModel).where(ComponentModel.id == component_id)
        result = await self._session.execute(stmt)
        return (getattr(result, "rowcount", 0) or 0) > 0
