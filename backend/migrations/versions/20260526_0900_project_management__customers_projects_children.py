"""project-management: customers + projects + project_children, plus FK on stock_events.project_id.

Revision ID: 20260526_0900
Revises: 20260525_2000
Create Date: 2026-05-26 09:00:00

Adds the top-layer entity (Project) and the minimal id-link surface for the
Holded customer. Mirrors the structure already shipped for modules:

- `customers`: id-link to Holded (UNIQUE case-insensitive on `holded_id`).
- `projects`: status enum (`Draft | Active | Delivered | Archived`),
  case-insensitive UNIQUE on `code`, optional FK to `customers`.
- `project_children`: XOR edge to a module or a component, with partial
  UNIQUE indexes so the same `(parent, child)` pair can't be duplicated
  (use `quantity` instead).
- Materializes the previously-deferred FK on `stock_events.project_id`,
  pointing at the new `projects` table with `ON DELETE SET NULL` so the
  ledger survives any future hard-delete of a project.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260526_0900"
down_revision: str | None = "20260525_2000"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ----- customers -----
    op.create_table(
        "customers",
        sa.Column(
            "id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("holded_id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("holded_url", sa.String(length=500), nullable=True),
        sa.Column("notas", sa.Text(), nullable=True),
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
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_customers_holded_id_lower "
        "ON customers (lower(holded_id))"
    )

    # ----- projects -----
    op.create_table(
        "projects",
        sa.Column(
            "id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("code", sa.String(length=40), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'Draft'"),
        ),
        sa.Column(
            "customer_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("customers.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("fecha_inicio", sa.Date(), nullable=True),
        sa.Column("fecha_entrega_estimada", sa.Date(), nullable=True),
        sa.Column("fecha_entrega_real", sa.Date(), nullable=True),
        sa.Column("notas", sa.Text(), nullable=True),
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
            "status IN ('Draft', 'Active', 'Delivered', 'Archived')",
            name="ck_projects_status",
        ),
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_projects_code_lower "
        "ON projects (lower(code))"
    )
    op.execute(
        "CREATE INDEX ix_projects_name_lower "
        "ON projects (lower(name))"
    )
    op.create_index("ix_projects_status", "projects", ["status"])
    op.create_index("ix_projects_customer_id", "projects", ["customer_id"])

    # ----- project_children -----
    op.create_table(
        "project_children",
        sa.Column(
            "id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "parent_project_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
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
            name="ck_project_children_xor_child",
        ),
        sa.CheckConstraint("quantity > 0", name="ck_project_children_quantity"),
    )
    op.create_index(
        "ix_project_children_parent_order",
        "project_children",
        ["parent_project_id", "sort_order"],
    )
    op.create_index(
        "ix_project_children_child_module",
        "project_children",
        ["child_module_id"],
    )
    op.create_index(
        "ix_project_children_child_component",
        "project_children",
        ["child_component_id"],
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_project_children_parent_child_module "
        "ON project_children (parent_project_id, child_module_id) "
        "WHERE child_module_id IS NOT NULL"
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_project_children_parent_child_component "
        "ON project_children (parent_project_id, child_component_id) "
        "WHERE child_component_id IS NOT NULL"
    )

    # ----- stock_events.project_id FK materialization -----
    op.create_foreign_key(
        "fk_stock_events_project",
        "stock_events",
        "projects",
        ["project_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_stock_events_project",
        "stock_events",
        type_="foreignkey",
    )

    op.execute("DROP INDEX IF EXISTS uq_project_children_parent_child_component")
    op.execute("DROP INDEX IF EXISTS uq_project_children_parent_child_module")
    op.drop_index(
        "ix_project_children_child_component",
        table_name="project_children",
    )
    op.drop_index(
        "ix_project_children_child_module",
        table_name="project_children",
    )
    op.drop_index(
        "ix_project_children_parent_order",
        table_name="project_children",
    )
    op.drop_table("project_children")

    op.drop_index("ix_projects_customer_id", table_name="projects")
    op.drop_index("ix_projects_status", table_name="projects")
    op.execute("DROP INDEX IF EXISTS ix_projects_name_lower")
    op.execute("DROP INDEX IF EXISTS uq_projects_code_lower")
    op.drop_table("projects")

    op.execute("DROP INDEX IF EXISTS uq_customers_holded_id_lower")
    op.drop_table("customers")
