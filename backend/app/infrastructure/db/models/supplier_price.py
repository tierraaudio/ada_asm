"""SQLAlchemy model for the `supplier_prices` table."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base, TimestampMixin


class SupplierPriceModel(Base, TimestampMixin):
    __tablename__ = "supplier_prices"
    __table_args__ = (
        CheckConstraint("price >= 0", name="ck_supplier_prices_price"),
        CheckConstraint(
            "qty_tier IN (1, 10, 100, 1000)",
            name="ck_supplier_prices_qty_tier",
        ),
        UniqueConstraint(
            "component_id",
            "supplier_id",
            "qty_tier",
            "valid_from",
            name="uq_supplier_prices_component_supplier_qty_valid_from",
        ),
        Index(
            "ix_supplier_prices_component_id_valid_from",
            "component_id",
            "valid_from",
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
    qty_tier: Mapped[int] = mapped_column(Integer, nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    valid_from: Mapped[date] = mapped_column(Date, nullable=False)
