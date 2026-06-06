"""Repository contract for the `Customer` aggregate."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from app.domain.entities.customer import Customer


class CustomerRepository(Protocol):
    async def list_customers(self) -> list[Customer]: ...

    async def get_by_id(self, customer_id: UUID) -> Customer | None: ...

    async def get_by_holded_id(self, holded_id: str) -> Customer | None: ...

    async def save(self, customer: Customer) -> Customer: ...

    async def update(self, customer: Customer) -> Customer: ...

    async def delete(self, customer_id: UUID) -> bool: ...
