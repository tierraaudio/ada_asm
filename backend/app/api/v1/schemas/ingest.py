"""Request/response schemas for `POST /api/v1/components/ingest`.

The response carries the created component plus a structured `IngestionReport`
so a future frontend can render a results view without re-deriving anything.
See change `ingest-component-from-mpn` (component-ingestion).
"""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, NonNegativeInt

from app.api.v1.schemas.components import ComponentResponse


class IngestComponentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mpn: Annotated[str, Field(min_length=1, max_length=100)]
    ubicacion: Annotated[str | None, Field(default=None, max_length=100)] = None
    stock_inicial: NonNegativeInt | None = None
    holded_id: Annotated[str | None, Field(default=None, max_length=80)] = None
    force: bool = False


class IngestionFamilyBlock(BaseModel):
    inferred: str | None = None
    needs_review: bool = False
    decided_by: str | None = None
    match_type: str | None = None
    raw_category: str | None = None
    confidence: int | None = None


class IngestionDatasheetBlock(BaseModel):
    outcome: str  # archived | link_only | none
    source: str | None = None
    url: str | None = None
    blob_path: str | None = None
    size_bytes: int | None = None


class IngestionReportResponse(BaseModel):
    status: str  # ok | ok_with_warnings
    mpn: str
    sku: str
    sources_consulted: list[str] = Field(default_factory=list)
    sources_succeeded: list[str] = Field(default_factory=list)
    sources_contributed: list[str] = Field(default_factory=list)
    family: IngestionFamilyBlock
    datasheet: IngestionDatasheetBlock
    fields_populated: list[str] = Field(default_factory=list)
    fields_missing: list[str] = Field(default_factory=list)
    counts: dict[str, int] = Field(default_factory=dict)
    manual_overrides_applied: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class IngestComponentResponse(BaseModel):
    component: ComponentResponse
    report: IngestionReportResponse
