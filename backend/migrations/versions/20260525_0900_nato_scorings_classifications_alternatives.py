"""NATO scoring audit trail + per-scoring classifications + alternatives.

Revision ID: 20260525_0900
Revises: 20260524_1200
Create Date: 2026-05-25 09:00:00

- Drops ``components.verificado`` (now derived from the active scoring).
- ``components.nato_score`` / ``tier`` stay as denormalised caches of the
  currently-active scoring (read-fast for the list page).
- Adds ``component_nato_scorings`` (id, component_id, score, tier, classified_at,
  expires_at, classified_by_user_id, status, notes) with a partial UNIQUE
  index enforcing one ``active`` scoring per component.
- Adds ``scoring_classifications`` (sub-parts of the component analysed by
  that scoring; reference_component_id XOR reference_url XOR none).
- Adds ``scoring_alternatives`` (other catalogue components proposed as
  drop-in replacements **for this specific scoring**; no symmetric
  enforcement because each scoring owns its own list).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260525_0900"
down_revision: str | None = "20260524_1200"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # `verificado` becomes a derived value (component has an active scoring
    # whose `expires_at >= today`). Drop the column.
    op.drop_column("components", "verificado")

    op.create_table(
        "component_nato_scorings",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("component_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("nato_score", sa.String(length=2), nullable=False),
        sa.Column("tier", sa.Integer(), nullable=False),
        sa.Column("classified_at", sa.Date(), nullable=False),
        sa.Column("expires_at", sa.Date(), nullable=False),
        sa.Column(
            "classified_by_user_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column(
            "status",
            sa.String(length=10),
            nullable=False,
            server_default=sa.text("'active'"),
        ),
        sa.Column("notes", sa.Text(), nullable=True),
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
            name="fk_nato_scorings_component_id_components",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["classified_by_user_id"],
            ["users.id"],
            name="fk_nato_scorings_classified_by_user_id_users",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_component_nato_scorings"),
        sa.CheckConstraint(
            "nato_score IN ('A+', 'A', 'B', 'C', 'D', 'F')",
            name="ck_nato_scorings_nato_score",
        ),
        sa.CheckConstraint(
            "tier IN (1, 2, 3, 4)",
            name="ck_nato_scorings_tier",
        ),
        sa.CheckConstraint(
            "status IN ('active', 'archived')",
            name="ck_nato_scorings_status",
        ),
        sa.CheckConstraint(
            "expires_at >= classified_at",
            name="ck_nato_scorings_expires_after_classified",
        ),
    )
    op.create_index(
        "ix_nato_scorings_component_id_classified_at",
        "component_nato_scorings",
        ["component_id", sa.text("classified_at DESC")],
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_nato_scorings_one_active_per_component "
        "ON component_nato_scorings (component_id) WHERE status = 'active'"
    )

    op.create_table(
        "scoring_classifications",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "nato_scoring_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("part_label", sa.String(length=200), nullable=False),
        sa.Column("fabricante", sa.String(length=120), nullable=True),
        sa.Column("country_of_origin", sa.String(length=2), nullable=True),
        sa.Column("nato_score", sa.String(length=2), nullable=True),
        sa.Column(
            "verificado",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("notas", sa.Text(), nullable=True),
        sa.Column(
            "reference_component_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column("reference_url", sa.Text(), nullable=True),
        sa.Column(
            "sort_order",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
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
            ["nato_scoring_id"],
            ["component_nato_scorings.id"],
            name="fk_scoring_classifications_scoring_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["reference_component_id"],
            ["components.id"],
            name="fk_scoring_classifications_reference_component_id",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_scoring_classifications"),
        sa.CheckConstraint(
            "nato_score IS NULL OR "
            "nato_score IN ('A+', 'A', 'B', 'C', 'D', 'F')",
            name="ck_scoring_classifications_nato_score",
        ),
        sa.CheckConstraint(
            "reference_component_id IS NULL OR reference_url IS NULL",
            name="ck_scoring_classifications_reference_mutex",
        ),
    )
    op.create_index(
        "ix_scoring_classifications_scoring_id_sort_order",
        "scoring_classifications",
        ["nato_scoring_id", "sort_order"],
    )

    op.create_table(
        "scoring_alternatives",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "nato_scoring_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "alternative_component_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "sort_order",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
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
            ["nato_scoring_id"],
            ["component_nato_scorings.id"],
            name="fk_scoring_alternatives_scoring_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["alternative_component_id"],
            ["components.id"],
            name="fk_scoring_alternatives_alternative_component_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_scoring_alternatives"),
        sa.UniqueConstraint(
            "nato_scoring_id",
            "alternative_component_id",
            name="uq_scoring_alternatives_scoring_alt",
        ),
    )
    op.create_index(
        "ix_scoring_alternatives_scoring_id_sort_order",
        "scoring_alternatives",
        ["nato_scoring_id", "sort_order"],
    )
    op.create_index(
        "ix_scoring_alternatives_alternative_component_id",
        "scoring_alternatives",
        ["alternative_component_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_scoring_alternatives_alternative_component_id",
        table_name="scoring_alternatives",
    )
    op.drop_index(
        "ix_scoring_alternatives_scoring_id_sort_order",
        table_name="scoring_alternatives",
    )
    op.drop_table("scoring_alternatives")

    op.drop_index(
        "ix_scoring_classifications_scoring_id_sort_order",
        table_name="scoring_classifications",
    )
    op.drop_table("scoring_classifications")

    op.execute("DROP INDEX IF EXISTS uq_nato_scorings_one_active_per_component")
    op.drop_index(
        "ix_nato_scorings_component_id_classified_at",
        table_name="component_nato_scorings",
    )
    op.drop_table("component_nato_scorings")

    op.add_column(
        "components",
        sa.Column(
            "verificado",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
