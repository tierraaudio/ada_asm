"""SQLAlchemy model for the `stock_events` table.

A single table with a `kind` discriminator covers four event types:

- Component-level: ``purchase`` (supplier delivered N units at €X each) and
  ``consumption`` (N units used by a project).
- Module-level: ``fabricated`` (the workshop built N module units, with
  fabrication cost) and ``delivered`` (N module units shipped to a Holded
  customer).

The polymorphic owner is enforced via XOR CHECK between `component_id` and
`module_id`. The per-kind columns are nullable at the DB level but enforced
by CHECK constraints — see the migration. The application layer should still
validate before insert.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base, TimestampMixin

STOCK_EVENT_KINDS = ("purchase", "consumption", "fabricated", "delivered")


class StockEventModel(Base, TimestampMixin):
    __tablename__ = "stock_events"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_stock_events_quantity"),
        CheckConstraint(
            "kind IN ('purchase', 'consumption', 'fabricated', 'delivered')",
            name="ck_stock_events_kind",
        ),
        CheckConstraint(
            "(component_id IS NOT NULL)::int + (module_id IS NOT NULL)::int = 1",
            name="ck_stock_events_xor_owner",
        ),
        CheckConstraint(
            "(kind <> 'purchase') OR "
            "(supplier_id IS NOT NULL AND unit_cost IS NOT NULL "
            "AND total_cost IS NOT NULL)",
            name="ck_stock_events_purchase_columns",
        ),
        CheckConstraint(
            "(kind <> 'consumption') OR "
            "(project_id IS NOT NULL OR project_name_snapshot IS NOT NULL)",
            name="ck_stock_events_consumption_columns",
        ),
        Index(
            "ix_stock_events_component_id_occurred_at",
            "component_id",
            "occurred_at",
        ),
        Index(
            "ix_stock_events_module_id_occurred_at",
            "module_id",
            "occurred_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    component_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("components.id", ondelete="CASCADE"),
        nullable=True,
    )
    module_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("modules.id", ondelete="CASCADE"),
        nullable=True,
    )
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    occurred_at: Mapped[date] = mapped_column(Date, nullable=False)
    notes: Mapped[str | None] = mapped_column(nullable=True)

    # purchase + fabricated economics
    supplier_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("suppliers.id", ondelete="SET NULL"),
        nullable=True,
    )
    unit_cost: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    total_cost: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)
    currency: Mapped[str] = mapped_column(
        String(3), nullable=False, default="EUR", server_default=text("'EUR'")
    )

    # consumption-only — `project_id` FK is left unconstrained until the
    # `projects` table lands; `project_name_snapshot` keeps the readable name.
    project_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    project_name_snapshot: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # delivered-only — link to Holded CRM record + denormalised customer name.
    customer_id_holded: Mapped[str | None] = mapped_column(String(80), nullable=True)
    customer_name_snapshot: Mapped[str | None] = mapped_column(String(200), nullable=True)
