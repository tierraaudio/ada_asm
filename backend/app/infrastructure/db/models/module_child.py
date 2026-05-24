"""SQLAlchemy model for the `module_children` table — DAG edges."""

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


class ModuleChildModel(Base, TimestampMixin):
    __tablename__ = "module_children"
    __table_args__ = (
        # Exactly one of child_module_id / child_component_id must be set (XOR).
        CheckConstraint(
            "(child_module_id IS NOT NULL)::int + (child_component_id IS NOT NULL)::int = 1",
            name="ck_module_children_xor_child",
        ),
        # No direct self-reference.
        CheckConstraint(
            "child_module_id IS NULL OR child_module_id <> parent_module_id",
            name="ck_module_children_no_self_ref",
        ),
        CheckConstraint("quantity > 0", name="ck_module_children_quantity"),
        # Non-unique indexes for FK lookups + ordered child listing.
        Index(
            "ix_module_children_parent_order",
            "parent_module_id",
            "sort_order",
        ),
        Index("ix_module_children_child_module", "child_module_id"),
        Index("ix_module_children_child_component", "child_component_id"),
        # Partial UNIQUE indexes are created in the migration via op.execute()
        # because SQLAlchemy autogenerate can't express the WHERE clause.
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    parent_module_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("modules.id", ondelete="CASCADE"),
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
