"""SQLAlchemy model for `component_nato_scorings` (audit trail of OTAN scores)."""

from __future__ import annotations

from datetime import date
from uuid import UUID

from sqlalchemy import CheckConstraint, Date, ForeignKey, Index, Integer, String, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base, TimestampMixin

NATO_SCORING_STATUSES = ("active", "archived")


class ComponentNatoScoringModel(Base, TimestampMixin):
    __tablename__ = "component_nato_scorings"
    __table_args__ = (
        CheckConstraint(
            "nato_score IN ('A+', 'A', 'B', 'C', 'D', 'F')",
            name="ck_nato_scorings_nato_score",
        ),
        CheckConstraint("tier IN (1, 2, 3, 4)", name="ck_nato_scorings_tier"),
        CheckConstraint(
            "status IN ('active', 'archived')",
            name="ck_nato_scorings_status",
        ),
        CheckConstraint(
            "expires_at >= classified_at",
            name="ck_nato_scorings_expires_after_classified",
        ),
        # The "one active per component" partial index is created by Alembic
        # via op.execute(...) since SQLAlchemy autogenerate cannot express it.
        Index(
            "ix_nato_scorings_component_id_classified_at",
            "component_id",
            text("classified_at DESC"),
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
    nato_score: Mapped[str] = mapped_column(String(2), nullable=False)
    tier: Mapped[int] = mapped_column(Integer, nullable=False)
    classified_at: Mapped[date] = mapped_column(Date, nullable=False)
    expires_at: Mapped[date] = mapped_column(Date, nullable=False)
    classified_by_user_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(
        String(10), nullable=False, default="active", server_default=text("'active'")
    )
    notes: Mapped[str | None] = mapped_column(nullable=True)
