"""RefreshToken domain entity.

The ``RefreshToken`` row tracks the lifecycle of a long-lived refresh JWT. We
do NOT store the JWT itself — only a SHA-256 hex digest of the JWT's ``jti``
claim, which makes the row indexable and replay-detectable without making it
worth stealing from the database.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID, uuid4


@dataclass
class RefreshToken:
    id: UUID = field(default_factory=uuid4)
    user_id: UUID = field(default_factory=uuid4)
    jti_hash: str = ""
    expires_at: datetime | None = None
    revoked_at: datetime | None = None
    created_at: datetime | None = None
    created_from_ip: str | None = None
    user_agent: str | None = None

    @property
    def is_revoked(self) -> bool:
        return self.revoked_at is not None
