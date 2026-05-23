"""SQLAlchemy-backed implementation of `ComponentPurchaseRepository`."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.component_purchase import ComponentPurchase
from app.domain.repositories.component_purchase_repository import (
    ComponentPurchasePage,
)
from app.infrastructure.db.models.component_purchase import ComponentPurchaseModel


def _to_entity(row: ComponentPurchaseModel) -> ComponentPurchase:
    return ComponentPurchase(
        id=row.id,
        component_id=row.component_id,
        purchased_at=row.purchased_at,
        quantity=row.quantity,
        supplier=row.supplier,
        unit_cost=row.unit_cost,
        total_cost=row.total_cost,
        currency=row.currency,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


class SqlAlchemyComponentPurchaseRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_for_component(
        self,
        *,
        component_id: UUID,
        page: int,
        page_size: int,
    ) -> ComponentPurchasePage:
        base_stmt = select(ComponentPurchaseModel).where(
            ComponentPurchaseModel.component_id == component_id
        )
        count_stmt = select(func.count()).select_from(base_stmt.subquery())
        total = int((await self._session.execute(count_stmt)).scalar_one())

        offset = (page - 1) * page_size
        stmt = (
            base_stmt.order_by(ComponentPurchaseModel.purchased_at.desc())
            .limit(page_size)
            .offset(offset)
        )
        result = await self._session.execute(stmt)
        items = [_to_entity(row) for row in result.scalars().all()]
        return ComponentPurchasePage(
            items=items, total=total, page=page, page_size=page_size
        )

    async def save(self, purchase: ComponentPurchase) -> ComponentPurchase:
        row = ComponentPurchaseModel(
            id=purchase.id,
            component_id=purchase.component_id,
            purchased_at=purchase.purchased_at,
            quantity=purchase.quantity,
            supplier=purchase.supplier,
            unit_cost=purchase.unit_cost,
            total_cost=purchase.total_cost,
            currency=purchase.currency,
        )
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        return _to_entity(row)
