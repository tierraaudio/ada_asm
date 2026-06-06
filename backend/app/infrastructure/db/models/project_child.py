"""SQLAlchemy model for the `project_children` table — DAG edges from a project.

Mirrors `module_children`: polymorphic XOR child reference. No cycle constraint
needed since projects can't be hijos.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base, TimestampMixin


class ProjectChildModel(Base, TimestampMixin):
    __tablename__ = "project_children"
    __table_args__ = (
        CheckConstraint(
            "(child_module_id IS NOT NULL)::int + (child_component_id IS NOT NULL)::int = 1",
            name="ck_project_children_xor_child",
        ),
        CheckConstraint("quantity > 0", name="ck_project_children_quantity"),
        Index(
            "ix_project_children_parent_order",
            "parent_project_id",
            "sort_order",
        ),
        Index("ix_project_children_child_module", "child_module_id"),
        Index("ix_project_children_child_component", "child_component_id"),
        # Partial UNIQUE indexes are created in the migration via op.execute().
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    parent_project_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    child_module_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("modules.id", ondelete="CASCADE"),
        nullable=True,
    )
    child_component_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("components.id", ondelete="CASCADE"),
        nullable=True,
    )
    quantity: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    sort_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
    )
    notes: Mapped[str | None] = mapped_column(nullable=True)
