"""Supplier domain entity — distributors / vendors used across the catalogue."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID, uuid4


@dataclass
class Supplier:
    id: UUID = field(default_factory=uuid4)
    name: str = ""
    created_at: datetime | None = None
    updated_at: datetime | None = None
