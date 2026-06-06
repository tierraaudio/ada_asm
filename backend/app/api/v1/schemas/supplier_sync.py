"""Pydantic schemas for the `/supplier-sync/*` admin endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

SupplierCodeLiteral = Literal["mouser", "digikey", "tme", "farnell", "rs"]
RunStatusLiteral = Literal["running", "success", "partial", "failed"]
ErrorCodeLiteral = Literal[
    "RATE_LIMITED",
    "NOT_FOUND",
    "HTTP_5XX",
    "PARSE_ERROR",
    "AUTH_FAILED",
    "FX_UNAVAILABLE",
    "TIMEOUT",
    "UNKNOWN",
]


class SupplierSyncRunResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    supplier: SupplierCodeLiteral
    started_at: datetime
    finished_at: datetime | None = None
    components_processed: int
    components_updated: int
    errors_count: int
    status: RunStatusLiteral
    error_summary: str | None = None


class SupplierSyncErrorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    run_id: UUID
    component_id: UUID
    supplier: SupplierCodeLiteral
    error_code: ErrorCodeLiteral
    error_message: str
    occurred_at: datetime


class TriggerSyncResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: UUID = Field(
        ...,
        description=(
            "ID of the `supplier_sync_runs` row created. The task runs "
            "asynchronously; poll `GET /supplier-sync/runs/{id}` for "
            "completion."
        ),
    )
    task_id: str
