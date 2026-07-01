"""asm-legacy: traceability + obsolete columns on modules.

Revision ID: 20260701_1000
Revises: 20260615_1000
Create Date: 2026-07-01 10:00:00

The ASM assemblies (stock_items that are parents in stock_edges) migrate to ada
`modules`. These columns preserve the link to the old system and flag the many
items the old catalogue marked OBSOLETO so they can be filtered out of active
views without losing history.

- legacy_asm_id   ← old stock_items.id
- legacy_pn       ← old internal part number (also used as the module sku)
- migration_source ← provenance ('asm-legacy')
- migrated_at     ← when migrated
- obsolete        ← old item name contained "OBSOLETO"

All nullable except `obsolete` (default false); reversible.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260701_1000"
down_revision: str | None = "20260615_1000"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_LEGACY_COLUMNS: tuple[tuple[str, sa.types.TypeEngine], ...] = (
    ("legacy_asm_id", sa.String(length=64)),
    ("legacy_pn", sa.String(length=80)),
    ("migration_source", sa.String(length=32)),
    ("migrated_at", sa.DateTime(timezone=True)),
)


def upgrade() -> None:
    for name, col_type in _LEGACY_COLUMNS:
        op.add_column("modules", sa.Column(name, col_type, nullable=True))
    op.add_column(
        "modules",
        sa.Column("obsolete", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.create_index("ix_modules_legacy_asm_id", "modules", ["legacy_asm_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_modules_legacy_asm_id", table_name="modules")
    op.drop_column("modules", "obsolete")
    for name, _type in reversed(_LEGACY_COLUMNS):
        op.drop_column("modules", name)
