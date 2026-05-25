"""stock-events: polymorphic owner (component | module) + 2 new kinds for module-level fabricación / entrega.

Revision ID: 20260525_1800
Revises: 20260524_1938
Create Date: 2026-05-25 18:00:00

Extends `stock_events` so the same ledger can also record module-level
events:

- `fabricated` (kind): adds N module units to the warehouse — emitted when
  the team finishes building a module instance. Carries `unit_cost` /
  `total_cost` for fabrication accounting (mirrors purchase economics).
- `delivered` (kind): subtracts N module units — emitted when the order
  ships to a customer. Carries `customer_id_holded` (link to the Holded
  CRM record) and a denormalised `customer_name_snapshot` so the audit
  trail survives renames / deletes in Holded.

Polymorphic owner via XOR: every row references **exactly one** of
`component_id` or `module_id`. The old purchase/consumption events stay
on `component_id`; the new fabricated/delivered events sit on `module_id`.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260525_1800"
down_revision: str | None = "20260524_1938"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1) Drop NOT NULL on component_id (now nullable when module_id is set).
    op.alter_column("stock_events", "component_id", nullable=True)

    # 2) Add module_id FK (nullable; XOR with component_id).
    op.add_column(
        "stock_events",
        sa.Column(
            "module_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("modules.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )

    # 3) Customer fields for `delivered` events (text columns; the Holded
    #    record is referenced by id, name is denormalised for audit).
    op.add_column(
        "stock_events",
        sa.Column("customer_id_holded", sa.String(length=80), nullable=True),
    )
    op.add_column(
        "stock_events",
        sa.Column("customer_name_snapshot", sa.String(length=200), nullable=True),
    )

    # 4) Replace the old `kind` CHECK with the extended enum.
    op.drop_constraint("ck_stock_events_kind", "stock_events", type_="check")
    op.create_check_constraint(
        "ck_stock_events_kind",
        "stock_events",
        "kind IN ('purchase', 'consumption', 'fabricated', 'delivered')",
    )

    # 5) XOR: every row owns exactly one of (component_id, module_id).
    op.create_check_constraint(
        "ck_stock_events_xor_owner",
        "stock_events",
        "(component_id IS NOT NULL)::int + (module_id IS NOT NULL)::int = 1",
    )

    # 6) Index on the module-side for the same access pattern as the
    #    component-side index (ledger by date).
    op.create_index(
        "ix_stock_events_module_id_occurred_at",
        "stock_events",
        ["module_id", "occurred_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_stock_events_module_id_occurred_at", table_name="stock_events")
    op.drop_constraint("ck_stock_events_xor_owner", "stock_events", type_="check")
    op.drop_constraint("ck_stock_events_kind", "stock_events", type_="check")
    op.create_check_constraint(
        "ck_stock_events_kind",
        "stock_events",
        "kind IN ('purchase', 'consumption')",
    )
    op.drop_column("stock_events", "customer_name_snapshot")
    op.drop_column("stock_events", "customer_id_holded")
    op.drop_column("stock_events", "module_id")
    op.alter_column("stock_events", "component_id", nullable=False)
