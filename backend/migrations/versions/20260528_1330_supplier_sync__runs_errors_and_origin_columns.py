"""supplier-sync: runs + errors tables + last_supplier_sync_at + supplier_prices origin columns.

Revision ID: 20260528_1330
Revises: 20260526_1500
Create Date: 2026-05-28 13:30:00

Ships the schema for the supplier integration change:

- `supplier_sync_runs`: one row per daily/ad-hoc sync invocation, per
  supplier. Tracks `started_at`, `finished_at`, `components_processed`,
  `components_updated`, `errors_count`, `status` (`running | success |
  partial | failed`), optional `error_summary`.
- `supplier_sync_errors`: one row per (run, component, error). Bounded by
  retention later (out of scope for this migration). FK to runs and
  components cascade-delete on parent removal.
- `components.last_supplier_sync_at`: nullable, set by the daily Celery
  task on the first successful upsert for that component in the run.
- `supplier_prices.price_original` + `supplier_prices.currency_original`:
  preserve the supplier's native currency when the adapter normalises to
  EUR via cached FX. NULL on existing rows and on rows where FX could not
  be resolved.

Reversible: downgrade drops the new columns and the two new tables.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260528_1330"
down_revision: str | None = "20260526_1500"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


SUPPLIER_CODES = ("mouser", "digikey", "tme", "farnell", "rs")
RUN_STATUSES = ("running", "success", "partial", "failed")
ERROR_CODES = (
    "RATE_LIMITED",
    "NOT_FOUND",
    "HTTP_5XX",
    "PARSE_ERROR",
    "AUTH_FAILED",
    "FX_UNAVAILABLE",
    "TIMEOUT",
    "UNKNOWN",
)


def _in_clause(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{v}'" for v in values)


def upgrade() -> None:
    # ----- components.last_supplier_sync_at -----
    op.add_column(
        "components",
        sa.Column(
            "last_supplier_sync_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )

    # ----- supplier_prices: price_original + currency_original -----
    op.add_column(
        "supplier_prices",
        sa.Column("price_original", sa.Numeric(12, 4), nullable=True),
    )
    op.add_column(
        "supplier_prices",
        sa.Column("currency_original", sa.String(length=3), nullable=True),
    )

    # ----- supplier_sync_runs -----
    op.create_table(
        "supplier_sync_runs",
        sa.Column(
            "id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("supplier", sa.String(length=32), nullable=False),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "components_processed",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "components_updated",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "errors_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "status",
            sa.String(length=16),
            nullable=False,
            server_default=sa.text("'running'"),
        ),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            f"supplier IN ({_in_clause(SUPPLIER_CODES)})",
            name="ck_supplier_sync_runs_supplier",
        ),
        sa.CheckConstraint(
            f"status IN ({_in_clause(RUN_STATUSES)})",
            name="ck_supplier_sync_runs_status",
        ),
    )
    op.create_index(
        "ix_supplier_sync_runs_supplier_started_at",
        "supplier_sync_runs",
        ["supplier", sa.text("started_at DESC")],
    )
    op.create_index(
        "ix_supplier_sync_runs_status",
        "supplier_sync_runs",
        ["status"],
    )

    # ----- supplier_sync_errors -----
    op.create_table(
        "supplier_sync_errors",
        sa.Column(
            "id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "run_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("supplier_sync_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "component_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("components.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("supplier", sa.String(length=32), nullable=False),
        sa.Column("error_code", sa.String(length=64), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=False),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            f"supplier IN ({_in_clause(SUPPLIER_CODES)})",
            name="ck_supplier_sync_errors_supplier",
        ),
        sa.CheckConstraint(
            f"error_code IN ({_in_clause(ERROR_CODES)})",
            name="ck_supplier_sync_errors_error_code",
        ),
    )
    op.create_index(
        "ix_supplier_sync_errors_run_occurred",
        "supplier_sync_errors",
        ["run_id", sa.text("occurred_at DESC")],
    )
    op.create_index(
        "ix_supplier_sync_errors_component",
        "supplier_sync_errors",
        ["component_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_supplier_sync_errors_component",
        table_name="supplier_sync_errors",
    )
    op.drop_index(
        "ix_supplier_sync_errors_run_occurred",
        table_name="supplier_sync_errors",
    )
    op.drop_table("supplier_sync_errors")

    op.drop_index(
        "ix_supplier_sync_runs_status",
        table_name="supplier_sync_runs",
    )
    op.drop_index(
        "ix_supplier_sync_runs_supplier_started_at",
        table_name="supplier_sync_runs",
    )
    op.drop_table("supplier_sync_runs")

    op.drop_column("supplier_prices", "currency_original")
    op.drop_column("supplier_prices", "price_original")
    op.drop_column("components", "last_supplier_sync_at")
