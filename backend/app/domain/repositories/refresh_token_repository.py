"""Repository contract for ``RefreshToken``."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from app.domain.entities.refresh_token import RefreshToken


class RefreshTokenRepository(Protocol):
    async def save(self, token: RefreshToken) -> RefreshToken: ...

    async def get_by_jti_hash(self, jti_hash: str) -> RefreshToken | None: ...

    async def revoke(self, jti_hash: str) -> None: ...

    async def revoke_all_for_user(self, user_id: UUID) -> int: ...
