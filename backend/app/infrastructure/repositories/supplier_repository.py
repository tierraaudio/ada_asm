"""SQLAlchemy implementation of `SupplierRepository`."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.supplier import Supplier
from app.infrastructure.db.models.supplier import SupplierModel


def _to_entity(row: SupplierModel) -> Supplier:
    return Supplier(
        id=row.id,
        name=row.name,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


class SqlAlchemySupplierRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_all(self) -> list[Supplier]:
        stmt = select(SupplierModel).order_by(SupplierModel.name.asc())
        result = await self._session.execute(stmt)
        return [_to_entity(row) for row in result.scalars().all()]

    async def get_by_id(self, supplier_id: UUID) -> Supplier | None:
        row = await self._session.get(SupplierModel, supplier_id)
        return _to_entity(row) if row else None

    async def get_by_name(self, name: str) -> Supplier | None:
        stmt = select(SupplierModel).where(func.lower(SupplierModel.name) == name.lower())
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return _to_entity(row) if row else None

    async def save(self, supplier: Supplier) -> Supplier:
        row = SupplierModel(id=supplier.id, name=supplier.name)
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        return _to_entity(row)
