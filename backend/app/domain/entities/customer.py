"""Customer domain entity — id-link to Holded.

Thin entity that anchors a project to a Holded customer. `holded_id` is the
business key (case-insensitive unique) and `name` is denormalised so the UI
doesn't depend on Holded availability. The actual Holded sync lives in a
separate, future US.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID, uuid4


@dataclass
class Customer:
    id: UUID = field(default_factory=uuid4)
    holded_id: str = ""
    name: str = ""
    holded_url: str | None = None
    notas: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
