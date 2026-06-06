"""SQLAlchemy model for the `supplier_sync_runs` table."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, Index, Integer, String, Text, func, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base

SUPPLIER_CODES = ("mouser", "digikey", "tme", "farnell", "rs")
RUN_STATUSES = ("running", "success", "partial", "failed")


class SupplierSyncRunModel(Base):
    __tablename__ = "supplier_sync_runs"
    __table_args__ = (
        CheckConstraint(
            "supplier IN ('mouser', 'digikey', 'tme', 'farnell', 'rs')",
            name="ck_supplier_sync_runs_supplier",
        ),
        CheckConstraint(
            "status IN ('running', 'success', 'partial', 'failed')",
            name="ck_supplier_sync_runs_status",
        ),
        Index(
            "ix_supplier_sync_runs_supplier_started_at",
            "supplier",
            text("started_at DESC"),
        ),
        Index("ix_supplier_sync_runs_status", "status"),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    supplier: Mapped[str] = mapped_column(String(32), nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    components_processed: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
    )
    components_updated: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
    )
    errors_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
    )
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        server_default=text("'running'"),
    )
    error_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
