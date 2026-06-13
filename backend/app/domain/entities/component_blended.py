"""Domain entities for the per-supplier blended data.

Captured at MPN ingestion (change `ingest-component-from-mpn`): parametric
specs, compliance codes, documents (datasheets), and cross-references. Each
belongs to a component and records which supplier it came from.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID, uuid4


@dataclass
class ComponentParameter:
    component_id: UUID
    supplier: str
    label: str
    value: str
    key: str | None = None
    unit: str | None = None
    id: UUID = field(default_factory=uuid4)


@dataclass
class ComponentComplianceCode:
    component_id: UUID
    supplier: str
    code_type: str
    code_value: str
    id: UUID = field(default_factory=uuid4)


@dataclass
class ComponentDocument:
    component_id: UUID
    doc_type: str
    url: str
    supplier: str | None = None
    file_name: str | None = None
    size_bytes: int | None = None
    language: str | None = None
    blob_path: str | None = None
    sha256: str | None = None
    content_type: str | None = None
    fetched_at: datetime | None = None
    id: UUID = field(default_factory=uuid4)


@dataclass
class ComponentCrossRef:
    component_id: UUID
    supplier: str
    ref_type: str
    ref_value: str
    id: UUID = field(default_factory=uuid4)
