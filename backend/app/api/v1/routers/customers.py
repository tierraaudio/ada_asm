"""HTTP routes for the customers catalogue (Holded id-link)."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import get_db_session, require_user
from app.api.v1.schemas.projects import (
    CustomerCreateRequest,
    CustomerResponse,
    CustomerUpdateRequest,
)
from app.core.exceptions import CustomerNotFoundError
from app.domain.entities.customer import Customer
from app.domain.entities.user import User
from app.infrastructure.repositories.customer_repository import SqlAlchemyCustomerRepository

router = APIRouter(prefix="/customers", tags=["customers"])


def _repo(session: AsyncSession) -> SqlAlchemyCustomerRepository:
    return SqlAlchemyCustomerRepository(session)


@router.get("", response_model=list[CustomerResponse])
async def list_customers(
    _user: Annotated[User, Depends(require_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[CustomerResponse]:
    rows = await _repo(session).list_customers()
    return [CustomerResponse.model_validate(r) for r in rows]


@router.post("", response_model=CustomerResponse, status_code=status.HTTP_201_CREATED)
async def create_customer(
    payload: CustomerCreateRequest,
    _user: Annotated[User, Depends(require_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> CustomerResponse:
    created = await _repo(session).save(
        Customer(
            holded_id=payload.holded_id,
            name=payload.name,
            holded_url=payload.holded_url,
            notas=payload.notas,
        )
    )
    return CustomerResponse.model_validate(created)


@router.get("/{customer_id}", response_model=CustomerResponse)
async def get_customer(
    customer_id: UUID,
    _user: Annotated[User, Depends(require_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> CustomerResponse:
    row = await _repo(session).get_by_id(customer_id)
    if row is None:
        raise CustomerNotFoundError(f"customer not found: {customer_id}")
    return CustomerResponse.model_validate(row)


@router.patch("/{customer_id}", response_model=CustomerResponse)
async def patch_customer(
    customer_id: UUID,
    payload: CustomerUpdateRequest,
    _user: Annotated[User, Depends(require_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> CustomerResponse:
    repo = _repo(session)
    row = await repo.get_by_id(customer_id)
    if row is None:
        raise CustomerNotFoundError(f"customer not found: {customer_id}")
    fs = payload.model_fields_set
    if "holded_id" in fs and payload.holded_id is not None:
        row.holded_id = payload.holded_id
    if "name" in fs and payload.name is not None:
        row.name = payload.name
    if "holded_url" in fs:
        row.holded_url = payload.holded_url
    if "notas" in fs:
        row.notas = payload.notas
    updated = await repo.update(row)
    return CustomerResponse.model_validate(updated)


@router.delete("/{customer_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_customer(
    customer_id: UUID,
    _user: Annotated[User, Depends(require_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> None:
    await _repo(session).delete(customer_id)
