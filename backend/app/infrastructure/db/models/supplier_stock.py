"""SQLAlchemy model for the `supplier_stocks` table."""

from __future__ import annotations

from datetime import date
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    Integer,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base, TimestampMixin


class SupplierStockModel(Base, TimestampMixin):
    __tablename__ = "supplier_stocks"
    __table_args__ = (
        CheckConstraint("quantity >= 0", name="ck_supplier_stocks_quantity"),
        UniqueConstraint(
            "component_id",
            "supplier_id",
            "snapshot_at",
            name="uq_supplier_stocks_component_supplier_snapshot",
        ),
        Index(
            "ix_supplier_stocks_component_id_snapshot_at",
            "component_id",
            "snapshot_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    component_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("components.id", ondelete="CASCADE"),
        nullable=False,
    )
    supplier_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("suppliers.id", ondelete="CASCADE"),
        nullable=False,
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot_at: Mapped[date] = mapped_column(Date, nullable=False)
