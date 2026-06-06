"""ProjectInterestLink — sub-entity for the "Enlaces de interés" surface.

Each row is a `{name, url}` pair the user wants pinned to a project
(datasheets, references, internal docs…). Ordered by `sort_order`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID, uuid4


@dataclass
class ProjectInterestLink:
    id: UUID = field(default_factory=uuid4)
    project_id: UUID = field(default_factory=uuid4)
    name: str = ""
    url: str = ""
    sort_order: int = 0
    created_at: datetime | None = None
    updated_at: datetime | None = None
