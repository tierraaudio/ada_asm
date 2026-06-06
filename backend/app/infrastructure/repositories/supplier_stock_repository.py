"""SQLAlchemy implementation of `SupplierStockRepository`."""

from __future__ import annotations

from collections.abc import Iterable
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.supplier_stock import SupplierStock
from app.infrastructure.db.models.supplier import SupplierModel
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

    async def latest_summary_for_components(
        self, component_ids: Iterable[UUID]
    ) -> dict[UUID, list[tuple[UUID, str, int]]]:
        """Batched: most recent (supplier, quantity) per component, with name.

        Single round trip using PostgreSQL `DISTINCT ON` over
        `(component_id, supplier_id)` ordered by `snapshot_at DESC`. Avoids
        the N+1 that would result from calling `latest_for_component` per row.

        Returns `{component_id: [(supplier_id, supplier_name, quantity), ...]}`.
        Components without any snapshot are absent from the dict (callers
        default to an empty list).
        """
        ids = list(component_ids)
        if not ids:
            return {}
        stmt = (
            select(
                SupplierStockModel.component_id,
                SupplierStockModel.supplier_id,
                SupplierStockModel.quantity,
                SupplierModel.name,
            )
            .join(SupplierModel, SupplierModel.id == SupplierStockModel.supplier_id)
            .where(SupplierStockModel.component_id.in_(ids))
            .distinct(SupplierStockModel.component_id, SupplierStockModel.supplier_id)
            .order_by(
                SupplierStockModel.component_id,
                SupplierStockModel.supplier_id,
                SupplierStockModel.snapshot_at.desc(),
            )
        )
        result = await self._session.execute(stmt)
        out: dict[UUID, list[tuple[UUID, str, int]]] = {}
        for component_id, supplier_id, quantity, supplier_name in result.all():
            out.setdefault(component_id, []).append((supplier_id, supplier_name, quantity))
        return out

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
