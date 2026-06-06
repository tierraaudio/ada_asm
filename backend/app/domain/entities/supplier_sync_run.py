"""SupplierSyncRun domain entity — one row per sync invocation per supplier."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal
from uuid import UUID, uuid4

SupplierCode = Literal["mouser", "digikey", "tme", "farnell", "rs"]
RunStatus = Literal["running", "success", "partial", "failed"]


@dataclass
class SupplierSyncRun:
    id: UUID = field(default_factory=uuid4)
    supplier: SupplierCode = "mouser"
    started_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc),
    )
    finished_at: datetime | None = None
    components_processed: int = 0
    components_updated: int = 0
    errors_count: int = 0
    status: RunStatus = "running"
    error_summary: str | None = None
    created_at: datetime | None = None
