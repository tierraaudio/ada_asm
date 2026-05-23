"""component-management: components + component_purchases tables.

Revision ID: 20260523_1800
Revises: 20260513_1200
Create Date: 2026-05-23 18:00:00

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260523_1800"
down_revision: str | None = "20260513_1200"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "components",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("mpn", sa.String(length=100), nullable=False),
        sa.Column("sku", sa.String(length=100), nullable=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("family", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("datasheet_url", sa.Text(), nullable=True),
        sa.Column("location", sa.String(length=100), nullable=True),
        sa.Column("supplier", sa.String(length=100), nullable=True),
        sa.Column("price_per_100", sa.Numeric(precision=12, scale=4), nullable=True),
        sa.Column(
            "stock",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("tier", sa.String(length=2), nullable=False),
        sa.Column("nato_score", sa.String(length=20), nullable=False),
        sa.Column("country_of_origin", sa.String(length=2), nullable=True),
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
        sa.PrimaryKeyConstraint("id", name="pk_components"),
        sa.CheckConstraint("stock >= 0", name="ck_components_stock"),
        sa.CheckConstraint(
            "tier IN ('A+', 'A', 'B', 'C', 'D')",
            name="ck_components_tier",
        ),
        sa.CheckConstraint(
            "nato_score IN ('100_otan', 'otan', 'allied_otan', 'neutral', "
            "'high_risk', 'no_otan')",
            name="ck_components_nato_score",
        ),
    )
    op.create_index("ix_components_family_supplier", "components", ["family", "supplier"])
    # Functional indexes for case-insensitive search across the four columns we
    # surface in the list-page `?q=` query. The unique index on lower(mpn) is
    # the canonical business-key constraint (case-insensitive uniqueness).
    op.execute(
        "CREATE UNIQUE INDEX uq_components_mpn_lower ON components (lower(mpn))"
    )
    op.execute("CREATE INDEX ix_components_sku_lower ON components (lower(sku))")
    op.execute("CREATE INDEX ix_components_name_lower ON components (lower(name))")
    op.execute("CREATE INDEX ix_components_family_lower ON components (lower(family))")

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


def downgrade() -> None:
    op.drop_index(
        "ix_component_purchases_component_id_purchased_at",
        table_name="component_purchases",
    )
    op.drop_table("component_purchases")

    op.execute("DROP INDEX IF EXISTS ix_components_family_lower")
    op.execute("DROP INDEX IF EXISTS ix_components_name_lower")
    op.execute("DROP INDEX IF EXISTS ix_components_sku_lower")
    op.execute("DROP INDEX IF EXISTS uq_components_mpn_lower")
    op.drop_index("ix_components_family_supplier", table_name="components")
    op.drop_table("components")
