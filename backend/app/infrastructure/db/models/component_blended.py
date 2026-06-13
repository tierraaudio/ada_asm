"""SQLAlchemy models for the per-supplier blended tables.

Populated by the MPN ingestion pipeline (change `ingest-component-from-mpn`):
parameters, compliance codes, documents, cross-references, and the raw
JSONB payload snapshot per (component, supplier).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base, TimestampMixin


class ComponentParameterModel(Base, TimestampMixin):
    __tablename__ = "component_parameters"
    __table_args__ = (Index("ix_component_parameters_component", "component_id"),)

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    component_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("components.id", ondelete="CASCADE"),
        nullable=False,
    )
    supplier: Mapped[str] = mapped_column(String(32), nullable=False)
    param_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    param_label: Mapped[str] = mapped_column(String(255), nullable=False)
    param_value: Mapped[str] = mapped_column(Text, nullable=False)
    param_unit: Mapped[str | None] = mapped_column(String(64), nullable=True)


class ComponentComplianceModel(Base, TimestampMixin):
    __tablename__ = "component_compliance"
    __table_args__ = (Index("ix_component_compliance_component", "component_id"),)

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    component_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("components.id", ondelete="CASCADE"),
        nullable=False,
    )
    supplier: Mapped[str] = mapped_column(String(32), nullable=False)
    code_type: Mapped[str] = mapped_column(String(64), nullable=False)
    code_value: Mapped[str] = mapped_column(String(255), nullable=False)


class ComponentDocumentModel(Base, TimestampMixin):
    __tablename__ = "component_documents"
    __table_args__ = (
        Index("ix_component_documents_component", "component_id"),
        Index("ix_component_documents_sha256", "sha256"),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    component_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("components.id", ondelete="CASCADE"),
        nullable=False,
    )
    supplier: Mapped[str | None] = mapped_column(String(32), nullable=True)
    doc_type: Mapped[str] = mapped_column(String(32), nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    file_name: Mapped[str | None] = mapped_column(String(512), nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    language: Mapped[str | None] = mapped_column(String(16), nullable=True)
    blob_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    content_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    fetched_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class ComponentCrossRefModel(Base, TimestampMixin):
    __tablename__ = "component_cross_refs"
    __table_args__ = (Index("ix_component_cross_refs_component", "component_id"),)

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    component_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("components.id", ondelete="CASCADE"),
        nullable=False,
    )
    supplier: Mapped[str] = mapped_column(String(32), nullable=False)
    ref_type: Mapped[str] = mapped_column(String(32), nullable=False)
    ref_value: Mapped[str] = mapped_column(String(255), nullable=False)


class ComponentSupplierPayloadModel(Base, TimestampMixin):
    __tablename__ = "component_supplier_payloads"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    component_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("components.id", ondelete="CASCADE"),
        nullable=False,
    )
    supplier: Mapped[str] = mapped_column(String(32), nullable=False)
    raw_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
