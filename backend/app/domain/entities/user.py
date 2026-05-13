"""User domain entity.

A ``User`` represents a person authorised to use the system. It carries the
authoritative password hash (Argon2id) and the user's ``global_role``, which
the authentication layer reads to populate JWT claims. Per-project roles are
modelled separately in a future capability and are NOT a field on ``User``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal
from uuid import UUID, uuid4

GlobalRole = Literal["admin", "user"]


@dataclass
class User:
    id: UUID = field(default_factory=uuid4)
    email: str = ""
    password_hash: str = ""
    full_name: str = ""
    global_role: GlobalRole = "user"
    is_active: bool = True
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @property
    def role_display(self) -> str:
        """Capitalised role label shown in UI surfaces (e.g. 'Administrator', 'User')."""
        return "Administrator" if self.global_role == "admin" else "User"
