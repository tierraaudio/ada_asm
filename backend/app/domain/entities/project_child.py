"""ProjectChild — an edge in a Project's BOM.

Mirrors `ModuleChild` exactly: polymorphic owner via XOR — exactly one of
`child_module_id` / `child_component_id` is set per row. Enforced at the DB
level via CHECK constraint and by the service layer. No cycle detection is
needed because projects are never hijos.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID, uuid4


@dataclass
class ProjectChild:
    id: UUID = field(default_factory=uuid4)
    parent_project_id: UUID = field(default_factory=uuid4)
    child_module_id: UUID | None = None
    child_component_id: UUID | None = None
    quantity: int = 1
    sort_order: int = 0
    notes: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
