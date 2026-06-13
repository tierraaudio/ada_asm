"""ingest-component-from-mpn: blended scalar + family-provenance columns on components.

Revision ID: 20260613_1000
Revises: 20260528_1330
Create Date: 2026-06-13 10:00:00

Adds the columns populated by the MPN ingestion pipeline:

- Blended scalars from the supplier APIs (normalized at ingest, refreshable
  by the daily sync): lifecycle_status, last_buy_date, discontinued,
  end_of_life, moq, order_multiple, lead_time_days, unit_weight_kg,
  image_url. `country_of_origin` already exists from an earlier change and
  is simply populated at ingest.
- Family-inference provenance, so a mis-mapping is auditable and components
  can be re-classified in bulk without re-calling the supplier APIs:
  family_inferred_supplier, family_inferred_match_type, raw_category_id,
  raw_category_name, raw_tariff_code, family_confidence, family_needs_review.

Reversible: downgrade drops every column added here.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260613_1000"
down_revision: str | None = "20260528_1330"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Blended scalar columns (name, SQLAlchemy type).
_BLENDED_COLUMNS: tuple[tuple[str, sa.types.TypeEngine], ...] = (
    ("lifecycle_status", sa.String(length=32)),
    ("last_buy_date", sa.Date()),
    ("discontinued", sa.Boolean()),
    ("end_of_life", sa.Boolean()),
    ("moq", sa.Integer()),
    ("order_multiple", sa.Integer()),
    ("lead_time_days", sa.Integer()),
    ("unit_weight_kg", sa.Numeric(12, 6)),
    ("image_url", sa.Text()),
)

# Family-inference provenance columns (name, type, server_default).
_FAMILY_COLUMNS: tuple[tuple[str, sa.types.TypeEngine, str | None], ...] = (
    ("family_inferred_supplier", sa.String(length=32), None),
    ("family_inferred_match_type", sa.String(length=32), None),
    ("raw_category_id", sa.String(length=64), None),
    ("raw_category_name", sa.Text(), None),
    ("raw_tariff_code", sa.String(length=32), None),
    ("family_confidence", sa.SmallInteger(), None),
)


def upgrade() -> None:
    for name, col_type in _BLENDED_COLUMNS:
        op.add_column("components", sa.Column(name, col_type, nullable=True))

    for name, col_type, default in _FAMILY_COLUMNS:
        op.add_column(
            "components",
            sa.Column(name, col_type, nullable=True, server_default=default),
        )

    op.add_column(
        "components",
        sa.Column(
            "family_needs_review",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )


def downgrade() -> None:
    op.drop_column("components", "family_needs_review")
    for name, _type, _default in reversed(_FAMILY_COLUMNS):
        op.drop_column("components", name)
    for name, _type in reversed(_BLENDED_COLUMNS):
        op.drop_column("components", name)
