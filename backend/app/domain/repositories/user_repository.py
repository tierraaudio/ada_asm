"""Repository contract for the ``User`` aggregate."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from app.domain.entities.user import User


class UserRepository(Protocol):
    async def get_by_id(self, user_id: UUID) -> User | None: ...

    async def get_by_email(self, email: str) -> User | None: ...

    async def save(self, user: User) -> User: ...

    async def update_password(self, user_id: UUID, password_hash: str) -> None: ...

    async def count_admins(self) -> int: ...

    async def list_admins(self) -> list[User]: ...
