"""Repository contract for the `Supplier` aggregate."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from app.domain.entities.supplier import Supplier


class SupplierRepository(Protocol):
    async def list_all(self) -> list[Supplier]: ...

    async def get_by_id(self, supplier_id: UUID) -> Supplier | None: ...

    async def get_by_name(self, name: str) -> Supplier | None: ...

    async def save(self, supplier: Supplier) -> Supplier: ...
