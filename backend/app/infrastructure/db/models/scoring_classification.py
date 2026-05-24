"""SQLAlchemy model for `scoring_classifications` (sub-parts of one scoring)."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base, TimestampMixin


class ScoringClassificationModel(Base, TimestampMixin):
    __tablename__ = "scoring_classifications"
    __table_args__ = (
        CheckConstraint(
            "nato_score IS NULL OR nato_score IN ('A+', 'A', 'B', 'C', 'D', 'F')",
            name="ck_scoring_classifications_nato_score",
        ),
        CheckConstraint(
            "reference_component_id IS NULL OR reference_url IS NULL",
            name="ck_scoring_classifications_reference_mutex",
        ),
        Index(
            "ix_scoring_classifications_scoring_id_sort_order",
            "nato_scoring_id",
            "sort_order",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    nato_scoring_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("component_nato_scorings.id", ondelete="CASCADE"),
        nullable=False,
    )
    part_label: Mapped[str] = mapped_column(String(200), nullable=False)
    fabricante: Mapped[str | None] = mapped_column(String(120), nullable=True)
    country_of_origin: Mapped[str | None] = mapped_column(String(2), nullable=True)
    nato_score: Mapped[str | None] = mapped_column(String(2), nullable=True)
    verificado: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    notas: Mapped[str | None] = mapped_column(nullable=True)
    reference_component_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("components.id", ondelete="SET NULL"),
        nullable=True,
    )
    reference_url: Mapped[str | None] = mapped_column(nullable=True)
    sort_order: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
