"""SQLAlchemy model for the `components` table."""

from __future__ import annotations

from datetime import date
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    Integer,
    String,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base, TimestampMixin

TIER_VALUES = (1, 2, 3, 4)
NATO_SCORE_VALUES = ("A+", "A", "B", "C", "D", "F")


class ComponentModel(Base, TimestampMixin):
    __tablename__ = "components"
    __table_args__ = (
        CheckConstraint("stock >= 0", name="ck_components_stock"),
        CheckConstraint(
            "stock_min IS NULL OR stock_min >= 0",
            name="ck_components_stock_min",
        ),
        CheckConstraint("tier IN (1, 2, 3, 4)", name="ck_components_tier"),
        CheckConstraint(
            "nato_score IN ('A+', 'A', 'B', 'C', 'D', 'F')",
            name="ck_components_nato_score",
        ),
        Index("ix_components_family", "family"),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    mpn: Mapped[str] = mapped_column(String(100), nullable=False)
    sku: Mapped[str | None] = mapped_column(String(100), nullable=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    family: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(nullable=True)
    datasheet_url: Mapped[str | None] = mapped_column(nullable=True)
    location: Mapped[str | None] = mapped_column(String(100), nullable=True)
    fabricante: Mapped[str | None] = mapped_column(String(120), nullable=True)
    tipo_almacenamiento: Mapped[str | None] = mapped_column(String(80), nullable=True)
    holded_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    fecha_creacion: Mapped[date | None] = mapped_column(Date, nullable=True)
    notas: Mapped[str | None] = mapped_column(nullable=True)
    stock: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
    )
    stock_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tier: Mapped[int] = mapped_column(Integer, nullable=False)
    nato_score: Mapped[str] = mapped_column(String(2), nullable=False)
    country_of_origin: Mapped[str | None] = mapped_column(String(2), nullable=True)
    proveedor_preferente_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("suppliers.id", ondelete="SET NULL"),
        nullable=True,
    )
