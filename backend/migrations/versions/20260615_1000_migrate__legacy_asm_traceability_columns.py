"""asm-legacy migration: traceability columns on components.

Revision ID: 20260615_1000
Revises: 20260613_1002
Create Date: 2026-06-15 10:00:00

Adds columns that preserve the link back to the old ASM inventory system
(PostgreSQL `taasm.stock_items`) so a migrated component can always be traced
to its origin and so the old internal part number — the key the legacy BOM,
orders and history reference — is never lost:

- legacy_asm_id   ← old stock_items.id (exact row trace)
- legacy_pn       ← old internal part number (e.g. RM-COM-SMD-RES-187)
- migration_source ← provenance marker (e.g. 'asm-legacy')
- migrated_at     ← when the row was migrated
- cost            ← unit cost recorded in the old system (price baseline)

All nullable; reversible (downgrade drops them).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260615_1000"
down_revision: str | None = "20260613_1002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_LEGACY_COLUMNS: tuple[tuple[str, sa.types.TypeEngine], ...] = (
    ("legacy_asm_id", sa.String(length=64)),
    ("legacy_pn", sa.String(length=80)),
    ("migration_source", sa.String(length=32)),
    ("migrated_at", sa.DateTime(timezone=True)),
    ("cost", sa.Numeric(12, 4)),
)


def upgrade() -> None:
    for name, col_type in _LEGACY_COLUMNS:
        op.add_column("components", sa.Column(name, col_type, nullable=True))
    op.create_index(
        "ix_components_legacy_asm_id", "components", ["legacy_asm_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_components_legacy_asm_id", table_name="components")
    for name, _type in reversed(_LEGACY_COLUMNS):
        op.drop_column("components", name)
