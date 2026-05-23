"""SQLAlchemy model for the `components` table."""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from sqlalchemy import CheckConstraint, Index, Integer, Numeric, String, func, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base, TimestampMixin

TIER_VALUES = ("A+", "A", "B", "C", "D")
NATO_SCORE_VALUES = (
    "100_otan",
    "otan",
    "allied_otan",
    "neutral",
    "high_risk",
    "no_otan",
)


class ComponentModel(Base, TimestampMixin):
    __tablename__ = "components"
    __table_args__ = (
        CheckConstraint("stock >= 0", name="ck_components_stock"),
        CheckConstraint(
            "tier IN ('A+', 'A', 'B', 'C', 'D')",
            name="ck_components_tier",
        ),
        CheckConstraint(
            "nato_score IN ('100_otan', 'otan', 'allied_otan', 'neutral', 'high_risk', 'no_otan')",
            name="ck_components_nato_score",
        ),
        # The functional unique index on lower(mpn) is created by the Alembic
        # migration via an explicit op.execute(...) — SQLAlchemy autogenerate
        # cannot express functional indexes, so we register it operationally.
        Index("ix_components_family_supplier", "family", "supplier"),
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
    supplier: Mapped[str | None] = mapped_column(String(100), nullable=True)
    price_per_100: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    stock: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
    )
    tier: Mapped[str] = mapped_column(String(2), nullable=False)
    nato_score: Mapped[str] = mapped_column(String(20), nullable=False)
    country_of_origin: Mapped[str | None] = mapped_column(String(2), nullable=True)
