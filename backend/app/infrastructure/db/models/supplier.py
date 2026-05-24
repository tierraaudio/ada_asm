"""SQLAlchemy model for the `suppliers` table."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import String, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base, TimestampMixin


class SupplierModel(Base, TimestampMixin):
    __tablename__ = "suppliers"
    # The case-insensitive unique index `uq_suppliers_name_lower` is created
    # by the Alembic migration via `op.execute(...)` — functional indexes
    # cannot be expressed via SQLAlchemy autogenerate.

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    name: Mapped[str] = mapped_column(String(80), nullable=False)
