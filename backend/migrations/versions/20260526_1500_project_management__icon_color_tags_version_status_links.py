"""project-management: icon + color + tags + version on projects, Spanish status enum, interest_links table.

Revision ID: 20260526_1500
Revises: 20260526_0900
Create Date: 2026-05-26 15:00:00

Aligns the Project entity with the Figma source of truth:

- New columns on `projects`: `icon` (emoji), `color` (hex), `tags` (text[]),
  `version` (varchar(40)).
- Status enum migrated to Spanish to match the FE labels exactly:
  `Presupuestado | Esperando | En proceso | Completado | Archivado`.
  Existing rows are translated by the migration: Draft→Presupuestado,
  Active→En proceso, Delivered→Completado, Archived→Archivado.
- New table `project_interest_links` — sub-entity for the "Enlaces de interés"
  surface (add/edit/delete individual links per project).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260526_1500"
down_revision: str | None = "20260526_0900"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ----- projects: new columns -----
    op.add_column(
        "projects",
        sa.Column("icon", sa.String(length=8), nullable=True),
    )
    op.add_column(
        "projects",
        sa.Column("color", sa.String(length=7), nullable=True),
    )
    op.add_column(
        "projects",
        sa.Column(
            "tags",
            sa.dialects.postgresql.ARRAY(sa.String()),
            nullable=False,
            server_default=sa.text("ARRAY[]::varchar[]"),
        ),
    )
    op.add_column(
        "projects",
        sa.Column("version", sa.String(length=40), nullable=True),
    )

    # ----- projects: status enum migration (English → Spanish) -----
    op.drop_constraint("ck_projects_status", "projects", type_="check")
    op.execute(
        """
        UPDATE projects SET status = CASE status
            WHEN 'Draft' THEN 'Presupuestado'
            WHEN 'Active' THEN 'En proceso'
            WHEN 'Delivered' THEN 'Completado'
            WHEN 'Archived' THEN 'Archivado'
            ELSE status
        END
        """
    )
    op.alter_column(
        "projects",
        "status",
        server_default=sa.text("'Presupuestado'"),
    )
    op.create_check_constraint(
        "ck_projects_status",
        "projects",
        "status IN ('Presupuestado', 'Esperando', 'En proceso', 'Completado', 'Archivado')",
    )

    # ----- project_interest_links -----
    op.create_table(
        "project_interest_links",
        sa.Column(
            "id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "project_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("url", sa.String(length=2000), nullable=False),
        sa.Column(
            "sort_order",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
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
    op.create_index(
        "ix_project_interest_links_project_order",
        "project_interest_links",
        ["project_id", "sort_order"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_project_interest_links_project_order",
        table_name="project_interest_links",
    )
    op.drop_table("project_interest_links")

    op.drop_constraint("ck_projects_status", "projects", type_="check")
    op.execute(
        """
        UPDATE projects SET status = CASE status
            WHEN 'Presupuestado' THEN 'Draft'
            WHEN 'En proceso' THEN 'Active'
            WHEN 'Completado' THEN 'Delivered'
            WHEN 'Archivado' THEN 'Archived'
            WHEN 'Esperando' THEN 'Active'
            ELSE status
        END
        """
    )
    op.alter_column(
        "projects",
        "status",
        server_default=sa.text("'Draft'"),
    )
    op.create_check_constraint(
        "ck_projects_status",
        "projects",
        "status IN ('Draft', 'Active', 'Delivered', 'Archived')",
    )

    op.drop_column("projects", "version")
    op.drop_column("projects", "tags")
    op.drop_column("projects", "color")
    op.drop_column("projects", "icon")
