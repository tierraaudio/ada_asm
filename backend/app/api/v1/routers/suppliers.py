"""HTTP routes for suppliers (read-only listing for now)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import get_db_session, require_user
from app.api.v1.schemas.components import SupplierResponse
from app.application.services.suppliers_service import SuppliersService
from app.domain.entities.user import User
from app.infrastructure.repositories.supplier_repository import (
    SqlAlchemySupplierRepository,
)

router = APIRouter(prefix="/suppliers", tags=["suppliers"])


@router.get("", response_model=list[SupplierResponse])
async def list_suppliers(
    _user: Annotated[User, Depends(require_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[SupplierResponse]:
    service = SuppliersService(suppliers=SqlAlchemySupplierRepository(session))
    suppliers = await service.list_all()
    return [SupplierResponse.model_validate(s) for s in suppliers]
