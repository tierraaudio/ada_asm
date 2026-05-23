"""SQLAlchemy-backed implementation of `ComponentRepository`."""

from __future__ import annotations

from typing import cast
from uuid import UUID

from sqlalchemy import delete, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ComponentMpnAlreadyRegisteredError
from app.domain.entities.component import Component, NatoScoreValue, TierValue
from app.domain.repositories.component_repository import (
    ComponentFilters,
    ComponentPage,
)
from app.infrastructure.db.models.component import ComponentModel


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
        supplier=row.supplier,
        price_per_100=row.price_per_100,
        stock=row.stock,
        tier=cast(TierValue, row.tier),
        nato_score=cast(NatoScoreValue, row.nato_score),
        country_of_origin=row.country_of_origin,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _is_mpn_unique_violation(exc: IntegrityError) -> bool:
    """The unique index is `uq_components_mpn_lower` (functional, see migration).

    Postgres surfaces it in the orig message; we also accept the table-level
    constraint name as a fallback.
    """
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

        if filters.family is not None:
            stmt = stmt.where(ComponentModel.family == filters.family)
        if filters.supplier is not None:
            stmt = stmt.where(ComponentModel.supplier == filters.supplier)
        if filters.tier is not None:
            stmt = stmt.where(ComponentModel.tier == filters.tier)
        if filters.nato_score is not None:
            stmt = stmt.where(ComponentModel.nato_score == filters.nato_score)
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

        # Count BEFORE applying limit/offset.
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = int((await self._session.execute(count_stmt)).scalar_one())

        offset = (page - 1) * page_size
        stmt = stmt.order_by(ComponentModel.name.asc()).limit(page_size).offset(offset)
        result = await self._session.execute(stmt)
        items = [_to_entity(row) for row in result.scalars().all()]

        return ComponentPage(items=items, total=total, page=page, page_size=page_size)

    async def get_by_id(self, component_id: UUID) -> Component | None:
        row = await self._session.get(ComponentModel, component_id)
        return _to_entity(row) if row else None

    async def get_by_mpn(self, mpn: str) -> Component | None:
        stmt = select(ComponentModel).where(func.lower(ComponentModel.mpn) == mpn.lower())
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
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
            supplier=component.supplier,
            price_per_100=component.price_per_100,
            stock=component.stock,
            tier=component.tier,
            nato_score=component.nato_score,
            country_of_origin=component.country_of_origin,
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
        # mpn is intentionally NOT copied — it is immutable in this US.
        row.sku = component.sku
        row.name = component.name
        row.family = component.family
        row.description = component.description
        row.datasheet_url = component.datasheet_url
        row.location = component.location
        row.supplier = component.supplier
        row.price_per_100 = component.price_per_100
        row.stock = component.stock
        row.tier = component.tier
        row.nato_score = component.nato_score
        row.country_of_origin = component.country_of_origin
        await self._session.flush()
        await self._session.refresh(row)
        return _to_entity(row)

    async def delete(self, component_id: UUID) -> bool:
        stmt = delete(ComponentModel).where(ComponentModel.id == component_id)
        result = await self._session.execute(stmt)
        return (getattr(result, "rowcount", 0) or 0) > 0
