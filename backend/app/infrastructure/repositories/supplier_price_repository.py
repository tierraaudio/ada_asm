"""SQLAlchemy implementation of `SupplierPriceRepository`."""

from __future__ import annotations

from typing import cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.supplier_price import QtyTier, SupplierPrice
from app.infrastructure.db.models.supplier_price import SupplierPriceModel


def _to_entity(row: SupplierPriceModel) -> SupplierPrice:
    return SupplierPrice(
        id=row.id,
        component_id=row.component_id,
        supplier_id=row.supplier_id,
        qty_tier=cast(QtyTier, row.qty_tier),
        price=row.price,
        valid_from=row.valid_from,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


class SqlAlchemySupplierPriceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_for_component(self, component_id: UUID) -> list[SupplierPrice]:
        stmt = (
            select(SupplierPriceModel)
            .where(SupplierPriceModel.component_id == component_id)
            .order_by(SupplierPriceModel.valid_from.desc(), SupplierPriceModel.qty_tier.asc())
        )
        result = await self._session.execute(stmt)
        return [_to_entity(row) for row in result.scalars().all()]

    async def save(self, price: SupplierPrice) -> SupplierPrice:
        row = SupplierPriceModel(
            id=price.id,
            component_id=price.component_id,
            supplier_id=price.supplier_id,
            qty_tier=price.qty_tier,
            price=price.price,
            valid_from=price.valid_from,
        )
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        return _to_entity(row)
