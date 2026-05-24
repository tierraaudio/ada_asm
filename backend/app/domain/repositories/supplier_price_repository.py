"""Repository contract for `SupplierPrice`."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from app.domain.entities.supplier_price import SupplierPrice


class SupplierPriceRepository(Protocol):
    async def list_for_component(self, component_id: UUID) -> list[SupplierPrice]: ...

    async def save(self, price: SupplierPrice) -> SupplierPrice: ...
