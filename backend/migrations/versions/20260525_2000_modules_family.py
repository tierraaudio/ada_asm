"""module-management: add `family` column with Board | Device | Bundle enum.

Revision ID: 20260525_2000
Revises: 20260525_1800
Create Date: 2026-05-25 20:00:00

Adds a high-level classification axis to modules. Mirrors the
`components.family` axis (Microcontroladores / Sensores / …) but with a
distinct enum:

- ``Board``: a sub-assembly PCB / module (e.g. Etapa Driver, Filtro EMI).
- ``Device``: a complete instrumentable module (e.g. Sensor Ambiental,
  Sistema Potencia BLDC).
- ``Bundle``: a top-level system integrating other modules (e.g. Drone,
  Estación Meteorológica).
- ``Case``: a packaging / enclosure that ships the bundle (e.g. caja de
  transporte, rack).

Existing rows backfill to ``Board`` (the most generic value) so the column
can be NOT NULL without a separate two-step migration.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260525_2000"
down_revision: str | None = "20260525_1800"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "modules",
        sa.Column(
            "family",
            sa.String(length=40),
            nullable=False,
            server_default=sa.text("'Board'"),
        ),
    )
    op.create_check_constraint(
        "ck_modules_family",
        "modules",
        "family IN ('Board', 'Device', 'Bundle', 'Case')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_modules_family", "modules", type_="check")
    op.drop_column("modules", "family")
