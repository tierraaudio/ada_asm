"""Repository contract for ``PasswordResetToken``."""

from __future__ import annotations

from typing import Protocol

from app.domain.entities.password_reset_token import PasswordResetToken


class PasswordResetTokenRepository(Protocol):
    async def save(self, token: PasswordResetToken) -> PasswordResetToken: ...

    async def list_active(self) -> list[PasswordResetToken]: ...

    """Return every reset token whose ``used_at`` is NULL and ``expires_at``
    is in the future. The service verifies each Argon2 hash against the raw
    token presented by the user."""

    async def mark_used(self, token: PasswordResetToken) -> None: ...
