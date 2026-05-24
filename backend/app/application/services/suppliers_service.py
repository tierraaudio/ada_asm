"""Suppliers service — read-only listing for now."""

from __future__ import annotations

from app.domain.entities.supplier import Supplier
from app.domain.repositories.supplier_repository import SupplierRepository


class SuppliersService:
    def __init__(self, *, suppliers: SupplierRepository) -> None:
        self._suppliers = suppliers

    async def list_all(self) -> list[Supplier]:
        return await self._suppliers.list_all()
