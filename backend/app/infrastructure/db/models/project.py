"""SQLAlchemy model for the `projects` table."""

from __future__ import annotations

from datetime import date
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    Date,
    ForeignKey,
    String,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base, TimestampMixin


class ProjectModel(Base, TimestampMixin):
    __tablename__ = "projects"
    __table_args__ = (
        CheckConstraint(
            "status IN ('Presupuestado', 'Esperando', 'En proceso', 'Completado', 'Archivado')",
            name="ck_projects_status",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    code: Mapped[str] = mapped_column(String(40), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(nullable=True)
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default=text("'Presupuestado'"),
    )
    customer_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("customers.id", ondelete="SET NULL"),
        nullable=True,
    )
    icon: Mapped[str | None] = mapped_column(String(8), nullable=True)
    color: Mapped[str | None] = mapped_column(String(7), nullable=True)
    tags: Mapped[list[str]] = mapped_column(
        ARRAY(String()),
        nullable=False,
        server_default=text("ARRAY[]::varchar[]"),
    )
    version: Mapped[str | None] = mapped_column(String(40), nullable=True)
    fecha_inicio: Mapped[date | None] = mapped_column(Date, nullable=True)
    fecha_entrega_estimada: Mapped[date | None] = mapped_column(Date, nullable=True)
    fecha_entrega_real: Mapped[date | None] = mapped_column(Date, nullable=True)
    notas: Mapped[str | None] = mapped_column(nullable=True)
