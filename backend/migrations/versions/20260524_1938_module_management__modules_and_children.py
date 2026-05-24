"""module-management: modules + module_children (DAG of assemblies).

Revision ID: 20260524_1938
Revises: 20260525_0900
Create Date: 2026-05-24 19:38:22

Adds the catalogue of reusable modules and the DAG edge table connecting
modules to other modules or to components, with explicit per-edge
`quantity`.

Partial UNIQUE indexes (one per child kind) prevent duplicating the same
`(parent, child)` pair — to want N copies, raise `quantity`. The XOR
CHECK enforces that each edge points to exactly one of module/component.

Cycle detection is handled at the service layer via a `WITH RECURSIVE`
query before each `add_child`; the DB only blocks the trivial
self-reference case.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260524_1938"
down_revision: str | None = "20260525_0900"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ----- modules -----
    op.create_table(
        "modules",
        sa.Column(
            "id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("sku", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "version",
            sa.String(length=40),
            nullable=False,
            server_default=sa.text("'v1.0'"),
        ),
        sa.Column("fabricante", sa.String(length=120), nullable=True),
        sa.Column("location", sa.String(length=100), nullable=True),
        sa.Column("tipo_almacenamiento", sa.String(length=80), nullable=True),
        sa.Column(
            "stock",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("notas", sa.Text(), nullable=True),
        sa.Column("fecha_creacion", sa.Date(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint("stock >= 0", name="ck_modules_stock"),
    )

    # Functional indexes — written via raw SQL because SQLAlchemy autogenerate
    # can't express functional indexes.
    op.execute(
        "CREATE UNIQUE INDEX uq_modules_sku_lower "
        "ON modules (lower(sku))"
    )
    op.execute(
        "CREATE INDEX ix_modules_name_lower "
        "ON modules (lower(name))"
    )

    # ----- module_children -----
    op.create_table(
        "module_children",
        sa.Column(
            "id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "parent_module_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("modules.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "child_module_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("modules.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "child_component_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("components.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("quantity", sa.SmallInteger(), nullable=False),
        sa.Column(
            "sort_order",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "(child_module_id IS NOT NULL)::int + "
            "(child_component_id IS NOT NULL)::int = 1",
            name="ck_module_children_xor_child",
        ),
        sa.CheckConstraint(
            "child_module_id IS NULL OR child_module_id <> parent_module_id",
            name="ck_module_children_no_self_ref",
        ),
        sa.CheckConstraint("quantity > 0", name="ck_module_children_quantity"),
    )

    op.create_index(
        "ix_module_children_parent_order",
        "module_children",
        ["parent_module_id", "sort_order"],
    )
    op.create_index(
        "ix_module_children_child_module",
        "module_children",
        ["child_module_id"],
    )
    op.create_index(
        "ix_module_children_child_component",
        "module_children",
        ["child_component_id"],
    )

    # Partial UNIQUE indexes — autogenerate can't express WHERE clauses.
    op.execute(
        "CREATE UNIQUE INDEX uq_module_children_parent_child_module "
        "ON module_children (parent_module_id, child_module_id) "
        "WHERE child_module_id IS NOT NULL"
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_module_children_parent_child_component "
        "ON module_children (parent_module_id, child_component_id) "
        "WHERE child_component_id IS NOT NULL"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_module_children_parent_child_component")
    op.execute("DROP INDEX IF EXISTS uq_module_children_parent_child_module")
    op.drop_index("ix_module_children_child_component", table_name="module_children")
    op.drop_index("ix_module_children_child_module", table_name="module_children")
    op.drop_index("ix_module_children_parent_order", table_name="module_children")
    op.drop_table("module_children")

    op.execute("DROP INDEX IF EXISTS ix_modules_name_lower")
    op.execute("DROP INDEX IF EXISTS uq_modules_sku_lower")
    op.drop_table("modules")
