"""SQLAlchemy model for the `supplier_sync_errors` table."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base

ERROR_CODES = (
    "RATE_LIMITED",
    "NOT_FOUND",
    "HTTP_5XX",
    "PARSE_ERROR",
    "AUTH_FAILED",
    "FX_UNAVAILABLE",
    "TIMEOUT",
    "UNKNOWN",
)


class SupplierSyncErrorModel(Base):
    __tablename__ = "supplier_sync_errors"
    __table_args__ = (
        CheckConstraint(
            "supplier IN ('mouser', 'digikey', 'tme', 'farnell', 'rs')",
            name="ck_supplier_sync_errors_supplier",
        ),
        CheckConstraint(
            "error_code IN ('RATE_LIMITED', 'NOT_FOUND', 'HTTP_5XX', "
            "'PARSE_ERROR', 'AUTH_FAILED', 'FX_UNAVAILABLE', 'TIMEOUT', 'UNKNOWN')",
            name="ck_supplier_sync_errors_error_code",
        ),
        Index(
            "ix_supplier_sync_errors_run_occurred",
            "run_id",
            text("occurred_at DESC"),
        ),
        Index("ix_supplier_sync_errors_component", "component_id"),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    run_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("supplier_sync_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    component_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("components.id", ondelete="CASCADE"),
        nullable=False,
    )
    supplier: Mapped[str] = mapped_column(String(32), nullable=False)
    error_code: Mapped[str] = mapped_column(String(64), nullable=False)
    error_message: Mapped[str] = mapped_column(Text, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
