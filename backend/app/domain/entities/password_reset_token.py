"""PasswordResetToken domain entity.

A single-use token a user can redeem to reset their password. Stored as an
Argon2id hash of the URL-safe token string (higher entropy stretching than
the refresh-token sha256 because reset links travel via email and may be
observed by adversaries).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID, uuid4


@dataclass
class PasswordResetToken:
    id: UUID = field(default_factory=uuid4)
    user_id: UUID = field(default_factory=uuid4)
    token_hash: str = ""
    expires_at: datetime | None = None
    used_at: datetime | None = None
    created_at: datetime | None = None

    @property
    def is_used(self) -> bool:
        return self.used_at is not None
