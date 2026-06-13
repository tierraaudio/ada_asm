"""SQLAlchemy model for `component_family_rules`.

Editable seed table mapping each supplier's category signal (stable
category_id, HS tariff prefix, or localized name keyword) to one of our
internal families. Grows from logged misses without a code deploy.
See change `ingest-component-from-mpn` (family-inference capability).
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import Boolean, Index, SmallInteger, String, Text, func, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base, TimestampMixin


class ComponentFamilyRuleModel(Base, TimestampMixin):
    __tablename__ = "component_family_rules"
    __table_args__ = (
        Index(
            "ix_component_family_rules_lookup",
            "supplier",
            "match_type",
            "match_value",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    supplier: Mapped[str] = mapped_column(String(32), nullable=False)
    match_type: Mapped[str] = mapped_column(String(32), nullable=False)
    match_value: Mapped[str] = mapped_column(String(255), nullable=False)
    family: Mapped[str] = mapped_column(String(64), nullable=False)
    confidence: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, server_default=text("0")
    )
    priority: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, server_default=text("0")
    )
    enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
