"""Repository contract for `SupplierStock`."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from app.domain.entities.supplier_stock import SupplierStock


class SupplierStockRepository(Protocol):
    async def list_for_component(self, component_id: UUID) -> list[SupplierStock]: ...

    async def latest_for_component(self, component_id: UUID) -> list[SupplierStock]:
        """Most recent snapshot per supplier — used by the Stock badge logic."""
        ...

    async def save(self, stock: SupplierStock) -> SupplierStock: ...
