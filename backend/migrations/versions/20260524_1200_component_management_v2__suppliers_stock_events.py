"""component-management v2: real suppliers + supplier prices + supplier stock + stock events.

Revision ID: 20260524_1200
Revises: 20260523_1800
Create Date: 2026-05-24 12:00:00

This rework:

- Reshapes `components`: `tier` becomes INT (1-4), `nato_score` becomes VARCHAR
  in {A+, A, B, C, D, F}. Drops legacy denormalised `supplier` / `price_per_100`
  columns (replaced by `supplier_prices`). Adds `fabricante`,
  `tipo_almacenamiento`, `holded_id`, `fecha_creacion`, `verificado`, `notas`,
  `stock_min`, `proveedor_preferente_id`.
- Adds `suppliers` table.
- Adds `supplier_prices` (component × supplier × qty_tier × valid_from).
- Adds `supplier_stocks` (component × supplier × snapshot_at).
- Drops `component_purchases` and replaces it with `stock_events` (single table
  with `kind` discriminator: 'purchase' adds supplier/cost columns, 'consumption'
  references a future `projects` table — for now a snapshot string).

Component rows are TRUNCATEd in `upgrade()` because the value mapping for the
old `tier` / `nato_score` enums into the new shape is not deterministic — the
existing rows are seed-only and are recreated by `seed_components` after the
migration runs. The downgrade mirrors the same destructive contract.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260524_1200"
down_revision: str | None = "20260523_1800"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ---------- Drop the previous purchases table (replaced by stock_events) ----------
    op.drop_index(
        "ix_component_purchases_component_id_purchased_at",
        table_name="component_purchases",
    )
    op.drop_table("component_purchases")

    # ---------- Reshape `components` ----------
    # Wipe rows: the legacy enums are not deterministically convertible into
    # the new ones, and the data is seed-only.
    op.execute("TRUNCATE TABLE components RESTART IDENTITY CASCADE")

    # Drop the old enum-style columns and the legacy denormalised fields.
    op.drop_constraint("ck_components_tier", "components", type_="check")
    op.drop_constraint("ck_components_nato_score", "components", type_="check")
    op.drop_column("components", "tier")
    op.drop_column("components", "nato_score")
    op.drop_column("components", "supplier")
    op.drop_column("components", "price_per_100")

    # Re-add `tier` as INT 1..4 and `nato_score` as VARCHAR(2) in {A+, A, B, C, D, F}.
    op.add_column(
        "components",
        sa.Column("tier", sa.Integer(), nullable=False, server_default=sa.text("3")),
    )
    op.create_check_constraint(
        "ck_components_tier",
        "components",
        "tier IN (1, 2, 3, 4)",
    )
    op.add_column(
        "components",
        sa.Column(
            "nato_score",
            sa.String(length=2),
            nullable=False,
            server_default=sa.text("'C'"),
        ),
    )
    op.create_check_constraint(
        "ck_components_nato_score",
        "components",
        "nato_score IN ('A+', 'A', 'B', 'C', 'D', 'F')",
    )

    # New business columns.
    op.add_column("components", sa.Column("fabricante", sa.String(length=120), nullable=True))
    op.add_column(
        "components",
        sa.Column("tipo_almacenamiento", sa.String(length=80), nullable=True),
    )
    op.add_column("components", sa.Column("holded_id", sa.String(length=80), nullable=True))
    op.add_column("components", sa.Column("fecha_creacion", sa.Date(), nullable=True))
    op.add_column(
        "components",
        sa.Column(
            "verificado",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column("components", sa.Column("notas", sa.Text(), nullable=True))
    # `stock_min` nullable so we can fall back to tier*5 server-side or in FE.
    op.add_column("components", sa.Column("stock_min", sa.Integer(), nullable=True))
    op.create_check_constraint(
        "ck_components_stock_min",
        "components",
        "stock_min IS NULL OR stock_min >= 0",
    )

    # ---------- `suppliers` ----------
    op.create_table(
        "suppliers",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_suppliers"),
    )
    op.execute("CREATE UNIQUE INDEX uq_suppliers_name_lower ON suppliers (lower(name))")

    # Now wire `proveedor_preferente_id` on `components`.
    op.add_column(
        "components",
        sa.Column(
            "proveedor_preferente_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
    )
    op.create_foreign_key(
        "fk_components_proveedor_preferente_id_suppliers",
        source_table="components",
        referent_table="suppliers",
        local_cols=["proveedor_preferente_id"],
        remote_cols=["id"],
        ondelete="SET NULL",
    )

    # ---------- `supplier_prices` ----------
    op.create_table(
        "supplier_prices",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("component_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("supplier_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("qty_tier", sa.Integer(), nullable=False),
        sa.Column("price", sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column("valid_from", sa.Date(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["component_id"],
            ["components.id"],
            name="fk_supplier_prices_component_id_components",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["supplier_id"],
            ["suppliers.id"],
            name="fk_supplier_prices_supplier_id_suppliers",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_supplier_prices"),
        sa.CheckConstraint("price >= 0", name="ck_supplier_prices_price"),
        sa.CheckConstraint(
            "qty_tier IN (1, 10, 100, 1000)",
            name="ck_supplier_prices_qty_tier",
        ),
        sa.UniqueConstraint(
            "component_id",
            "supplier_id",
            "qty_tier",
            "valid_from",
            name="uq_supplier_prices_component_supplier_qty_valid_from",
        ),
    )
    op.create_index(
        "ix_supplier_prices_component_id_valid_from",
        "supplier_prices",
        ["component_id", "valid_from"],
    )

    # ---------- `supplier_stocks` ----------
    op.create_table(
        "supplier_stocks",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("component_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("supplier_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("snapshot_at", sa.Date(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["component_id"],
            ["components.id"],
            name="fk_supplier_stocks_component_id_components",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["supplier_id"],
            ["suppliers.id"],
            name="fk_supplier_stocks_supplier_id_suppliers",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_supplier_stocks"),
        sa.CheckConstraint("quantity >= 0", name="ck_supplier_stocks_quantity"),
        sa.UniqueConstraint(
            "component_id",
            "supplier_id",
            "snapshot_at",
            name="uq_supplier_stocks_component_supplier_snapshot",
        ),
    )
    op.create_index(
        "ix_supplier_stocks_component_id_snapshot_at",
        "supplier_stocks",
        ["component_id", "snapshot_at"],
    )

    # ---------- `stock_events` ----------
    op.create_table(
        "stock_events",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("component_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("occurred_at", sa.Date(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        # purchase-specific
        sa.Column("supplier_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("unit_cost", sa.Numeric(precision=12, scale=4), nullable=True),
        sa.Column("total_cost", sa.Numeric(precision=14, scale=4), nullable=True),
        sa.Column(
            "currency",
            sa.String(length=3),
            nullable=False,
            server_default=sa.text("'EUR'"),
        ),
        # consumption-specific (project_id FK will be wired when `projects`
        # lands; for now we keep a snapshot string so existing events survive)
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("project_name_snapshot", sa.String(length=200), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["component_id"],
            ["components.id"],
            name="fk_stock_events_component_id_components",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["supplier_id"],
            ["suppliers.id"],
            name="fk_stock_events_supplier_id_suppliers",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_stock_events"),
        sa.CheckConstraint("quantity > 0", name="ck_stock_events_quantity"),
        sa.CheckConstraint(
            "kind IN ('purchase', 'consumption')",
            name="ck_stock_events_kind",
        ),
        sa.CheckConstraint(
            "(kind <> 'purchase') OR "
            "(supplier_id IS NOT NULL AND unit_cost IS NOT NULL "
            "AND total_cost IS NOT NULL)",
            name="ck_stock_events_purchase_columns",
        ),
        sa.CheckConstraint(
            "(kind <> 'consumption') OR "
            "(project_id IS NOT NULL OR project_name_snapshot IS NOT NULL)",
            name="ck_stock_events_consumption_columns",
        ),
    )
    op.create_index(
        "ix_stock_events_component_id_occurred_at",
        "stock_events",
        ["component_id", "occurred_at"],
    )


def downgrade() -> None:
    # `stock_events` -> back to `component_purchases`
    op.drop_index(
        "ix_stock_events_component_id_occurred_at", table_name="stock_events"
    )
    op.drop_table("stock_events")

    op.drop_index(
        "ix_supplier_stocks_component_id_snapshot_at", table_name="supplier_stocks"
    )
    op.drop_table("supplier_stocks")

    op.drop_index(
        "ix_supplier_prices_component_id_valid_from", table_name="supplier_prices"
    )
    op.drop_table("supplier_prices")

    op.drop_constraint(
        "fk_components_proveedor_preferente_id_suppliers",
        "components",
        type_="foreignkey",
    )
    op.drop_column("components", "proveedor_preferente_id")

    op.execute("DROP INDEX IF EXISTS uq_suppliers_name_lower")
    op.drop_table("suppliers")

    op.drop_constraint("ck_components_stock_min", "components", type_="check")
    op.drop_column("components", "stock_min")
    op.drop_column("components", "notas")
    op.drop_column("components", "verificado")
    op.drop_column("components", "fecha_creacion")
    op.drop_column("components", "holded_id")
    op.drop_column("components", "tipo_almacenamiento")
    op.drop_column("components", "fabricante")

    op.drop_constraint("ck_components_nato_score", "components", type_="check")
    op.drop_constraint("ck_components_tier", "components", type_="check")
    op.drop_column("components", "nato_score")
    op.drop_column("components", "tier")

    op.execute("TRUNCATE TABLE components RESTART IDENTITY CASCADE")

    op.add_column(
        "components",
        sa.Column("supplier", sa.String(length=100), nullable=True),
    )
    op.add_column(
        "components",
        sa.Column("price_per_100", sa.Numeric(precision=12, scale=4), nullable=True),
    )
    op.add_column(
        "components",
        sa.Column(
            "tier",
            sa.String(length=2),
            nullable=False,
            server_default=sa.text("'C'"),
        ),
    )
    op.create_check_constraint(
        "ck_components_tier",
        "components",
        "tier IN ('A+', 'A', 'B', 'C', 'D')",
    )
    op.add_column(
        "components",
        sa.Column(
            "nato_score",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'neutral'"),
        ),
    )
    op.create_check_constraint(
        "ck_components_nato_score",
        "components",
        "nato_score IN ('100_otan', 'otan', 'allied_otan', 'neutral', "
        "'high_risk', 'no_otan')",
    )

    op.create_table(
        "component_purchases",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("component_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("purchased_at", sa.Date(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("supplier", sa.String(length=100), nullable=False),
        sa.Column("unit_cost", sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column("total_cost", sa.Numeric(precision=14, scale=4), nullable=False),
        sa.Column(
            "currency",
            sa.String(length=3),
            nullable=False,
            server_default=sa.text("'EUR'"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["component_id"],
            ["components.id"],
            name="fk_component_purchases_component_id_components",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_component_purchases"),
        sa.CheckConstraint("quantity > 0", name="ck_component_purchases_quantity"),
    )
    op.create_index(
        "ix_component_purchases_component_id_purchased_at",
        "component_purchases",
        ["component_id", "purchased_at"],
    )
