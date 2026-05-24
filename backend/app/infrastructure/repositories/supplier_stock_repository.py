"""SQLAlchemy implementation of `SupplierStockRepository`."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.supplier_stock import SupplierStock
from app.infrastructure.db.models.supplier_stock import SupplierStockModel


def _to_entity(row: SupplierStockModel) -> SupplierStock:
    return SupplierStock(
        id=row.id,
        component_id=row.component_id,
        supplier_id=row.supplier_id,
        quantity=row.quantity,
        snapshot_at=row.snapshot_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


class SqlAlchemySupplierStockRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_for_component(self, component_id: UUID) -> list[SupplierStock]:
        stmt = (
            select(SupplierStockModel)
            .where(SupplierStockModel.component_id == component_id)
            .order_by(SupplierStockModel.snapshot_at.desc())
        )
        result = await self._session.execute(stmt)
        return [_to_entity(row) for row in result.scalars().all()]

    async def latest_for_component(self, component_id: UUID) -> list[SupplierStock]:
        """Return the most recent snapshot per supplier (one row per supplier)."""
        all_rows = await self.list_for_component(component_id)
        latest_by_supplier: dict[UUID, SupplierStock] = {}
        for s in all_rows:
            sid = s.supplier_id
            if sid is None:
                continue
            current = latest_by_supplier.get(sid)
            if current is None or s.snapshot_at > current.snapshot_at:
                latest_by_supplier[sid] = s
        return list(latest_by_supplier.values())

    async def save(self, stock: SupplierStock) -> SupplierStock:
        row = SupplierStockModel(
            id=stock.id,
            component_id=stock.component_id,
            supplier_id=stock.supplier_id,
            quantity=stock.quantity,
            snapshot_at=stock.snapshot_at,
        )
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        return _to_entity(row)
