"""SQLAlchemy implementation of `StockEventRepository`."""

from __future__ import annotations

from typing import cast
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.stock_event import StockEvent, StockEventKind
from app.domain.repositories.stock_event_repository import StockEventPage
from app.infrastructure.db.models.stock_event import StockEventModel


def _to_entity(row: StockEventModel) -> StockEvent:
    return StockEvent(
        id=row.id,
        component_id=row.component_id,
        kind=cast(StockEventKind, row.kind),
        quantity=row.quantity,
        occurred_at=row.occurred_at,
        notes=row.notes,
        supplier_id=row.supplier_id,
        unit_cost=row.unit_cost,
        total_cost=row.total_cost,
        currency=row.currency,
        project_id=row.project_id,
        project_name_snapshot=row.project_name_snapshot,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


class SqlAlchemyStockEventRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_for_component(
        self,
        *,
        component_id: UUID,
        page: int,
        page_size: int,
    ) -> StockEventPage:
        base = select(StockEventModel).where(StockEventModel.component_id == component_id)
        total = int(
            (
                await self._session.execute(select(func.count()).select_from(base.subquery()))
            ).scalar_one()
        )
        offset = (page - 1) * page_size
        stmt = base.order_by(StockEventModel.occurred_at.desc()).limit(page_size).offset(offset)
        result = await self._session.execute(stmt)
        items = [_to_entity(row) for row in result.scalars().all()]
        return StockEventPage(items=items, total=total, page=page, page_size=page_size)

    async def save(self, event: StockEvent) -> StockEvent:
        row = StockEventModel(
            id=event.id,
            component_id=event.component_id,
            kind=event.kind,
            quantity=event.quantity,
            occurred_at=event.occurred_at,
            notes=event.notes,
            supplier_id=event.supplier_id,
            unit_cost=event.unit_cost,
            total_cost=event.total_cost,
            currency=event.currency,
            project_id=event.project_id,
            project_name_snapshot=event.project_name_snapshot,
        )
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        return _to_entity(row)
