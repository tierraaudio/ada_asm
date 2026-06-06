"""SupplierSyncError domain entity — one row per (run, component, error)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal
from uuid import UUID, uuid4

SupplierCode = Literal["mouser", "digikey", "tme", "farnell", "rs"]
ErrorCode = Literal[
    "RATE_LIMITED",
    "NOT_FOUND",
    "HTTP_5XX",
    "PARSE_ERROR",
    "AUTH_FAILED",
    "FX_UNAVAILABLE",
    "TIMEOUT",
    "UNKNOWN",
]


@dataclass
class SupplierSyncError:
    id: UUID = field(default_factory=uuid4)
    run_id: UUID | None = None
    component_id: UUID | None = None
    supplier: SupplierCode = "mouser"
    error_code: ErrorCode = "UNKNOWN"
    error_message: str = ""
    occurred_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc),
    )
