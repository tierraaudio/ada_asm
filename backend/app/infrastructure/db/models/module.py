"""SQLAlchemy model for the `modules` table."""

from __future__ import annotations

from datetime import date
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    Date,
    Integer,
    String,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base, TimestampMixin


class ModuleModel(Base, TimestampMixin):
    __tablename__ = "modules"
    __table_args__ = (
        CheckConstraint("stock >= 0", name="ck_modules_stock"),
        CheckConstraint(
            "family IN ('Board', 'Device', 'Bundle', 'Case')",
            name="ck_modules_family",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    sku: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(nullable=True)
    version: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        server_default=text("'v1.0'"),
    )
    family: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        server_default=text("'Board'"),
    )
    fabricante: Mapped[str | None] = mapped_column(String(120), nullable=True)
    location: Mapped[str | None] = mapped_column(String(100), nullable=True)
    tipo_almacenamiento: Mapped[str | None] = mapped_column(String(80), nullable=True)
    stock: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
    )
    notas: Mapped[str | None] = mapped_column(nullable=True)
    fecha_creacion: Mapped[date | None] = mapped_column(Date, nullable=True)
