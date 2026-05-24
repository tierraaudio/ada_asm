"""SQLAlchemy model for `scoring_alternatives` (alternatives proposed in a scoring)."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import ForeignKey, Index, Integer, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base, TimestampMixin


class ScoringAlternativeModel(Base, TimestampMixin):
    __tablename__ = "scoring_alternatives"
    __table_args__ = (
        UniqueConstraint(
            "nato_scoring_id",
            "alternative_component_id",
            name="uq_scoring_alternatives_scoring_alt",
        ),
        Index(
            "ix_scoring_alternatives_scoring_id_sort_order",
            "nato_scoring_id",
            "sort_order",
        ),
        Index(
            "ix_scoring_alternatives_alternative_component_id",
            "alternative_component_id",
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
    alternative_component_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("components.id", ondelete="CASCADE"),
        nullable=False,
    )
    notes: Mapped[str | None] = mapped_column(nullable=True)
    sort_order: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
