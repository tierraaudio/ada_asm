"""SQLAlchemy-backed implementation of `CustomerRepository`."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import CustomerHoldedIdAlreadyRegisteredError
from app.domain.entities.customer import Customer
from app.infrastructure.db.models.customer import CustomerModel


def _to_entity(row: CustomerModel) -> Customer:
    return Customer(
        id=row.id,
        holded_id=row.holded_id,
        name=row.name,
        holded_url=row.holded_url,
        notas=row.notas,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _is_holded_id_unique_violation(exc: IntegrityError) -> bool:
    return "uq_customers_holded_id_lower" in str(exc.orig).lower()


class SqlAlchemyCustomerRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_customers(self) -> list[Customer]:
        rows = (
            (await self._session.execute(select(CustomerModel).order_by(CustomerModel.name)))
            .scalars()
            .all()
        )
        return [_to_entity(r) for r in rows]

    async def get_by_id(self, customer_id: UUID) -> Customer | None:
        row = (
            await self._session.execute(
                select(CustomerModel).where(CustomerModel.id == customer_id)
            )
        ).scalar_one_or_none()
        return _to_entity(row) if row else None

    async def get_by_holded_id(self, holded_id: str) -> Customer | None:
        row = (
            await self._session.execute(
                select(CustomerModel).where(
                    func.lower(CustomerModel.holded_id) == holded_id.lower()
                )
            )
        ).scalar_one_or_none()
        return _to_entity(row) if row else None

    async def save(self, customer: Customer) -> Customer:
        row = CustomerModel(
            id=customer.id,
            holded_id=customer.holded_id,
            name=customer.name,
            holded_url=customer.holded_url,
            notas=customer.notas,
        )
        self._session.add(row)
        try:
            await self._session.flush()
        except IntegrityError as exc:
            await self._session.rollback()
            if _is_holded_id_unique_violation(exc):
                raise CustomerHoldedIdAlreadyRegisteredError(
                    f"holded_id already registered: {customer.holded_id}"
                ) from exc
            raise
        await self._session.commit()
        await self._session.refresh(row)
        return _to_entity(row)

    async def update(self, customer: Customer) -> Customer:
        row = (
            await self._session.execute(
                select(CustomerModel).where(CustomerModel.id == customer.id)
            )
        ).scalar_one_or_none()
        if row is None:
            raise LookupError(f"customer {customer.id} disappeared mid-update")
        row.holded_id = customer.holded_id
        row.name = customer.name
        row.holded_url = customer.holded_url
        row.notas = customer.notas
        try:
            await self._session.flush()
        except IntegrityError as exc:
            await self._session.rollback()
            if _is_holded_id_unique_violation(exc):
                raise CustomerHoldedIdAlreadyRegisteredError(
                    f"holded_id already registered: {customer.holded_id}"
                ) from exc
            raise
        await self._session.commit()
        await self._session.refresh(row)
        return _to_entity(row)

    async def delete(self, customer_id: UUID) -> bool:
        result = await self._session.execute(
            delete(CustomerModel).where(CustomerModel.id == customer_id)
        )
        await self._session.commit()
        return (getattr(result, "rowcount", 0) or 0) > 0
