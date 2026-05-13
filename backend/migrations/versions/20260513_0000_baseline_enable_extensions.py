"""baseline: enable required PostgreSQL extensions.

Revision ID: 20260513_0000
Revises:
Create Date: 2026-05-13 00:00:00

"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20260513_0000"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # pgcrypto: gen_random_uuid() for UUIDv4 server-side defaults.
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    # ltree: hierarchical paths for the Project / Module / Component tree.
    op.execute("CREATE EXTENSION IF NOT EXISTS ltree")


def downgrade() -> None:
    op.execute("DROP EXTENSION IF EXISTS ltree")
    op.execute("DROP EXTENSION IF EXISTS pgcrypto")
