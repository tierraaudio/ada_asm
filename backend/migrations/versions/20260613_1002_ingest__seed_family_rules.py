"""ingest-component-from-mpn: seed component_family_rules from supplier research.

Revision ID: 20260613_1002
Revises: 20260613_1001
Create Date: 2026-06-13 10:02:00

Seeds the initial family-mapping rules derived from live supplier probes
(see openspec/changes/ingest-component-from-mpn/research/). Confidence
encodes signal strength: stable category_id = 100, HS tariff_prefix = 70,
localized name_keyword = 40. The table grows from logged misses afterwards.

`name_keyword` match_values are stored NFKD-normalized (lowercase, accents
stripped) so the runtime matcher compares apples to apples. Ambiguous HS
buckets (e.g. 85423990 = sensors AND regulators) are intentionally NOT
seeded as tariff rules — disambiguated by Farnell name_keyword instead.

Idempotent (ON CONFLICT DO NOTHING). Reversible: downgrade deletes exactly
the rows seeded here, leaving any operator-added rules intact.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260613_1002"
down_revision: str | None = "20260613_1001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# (supplier, match_type, match_value, family, confidence)
_SEED: tuple[tuple[str, str, str, str, int], ...] = (
    # ---- DigiKey leaf CategoryId (stable, locale-invariant) ----
    ("digikey", "category_id", "280", "Diodos", 100),
    ("digikey", "category_id", "278", "Transistores", 100),
    ("digikey", "category_id", "685", "Microcontroladores", 100),
    ("digikey", "category_id", "525", "Sensores", 100),
    ("digikey", "category_id", "60", "Condensadores", 100),
    ("digikey", "category_id", "52", "Resistencias", 100),
    ("digikey", "category_id", "314", "Conectores", 100),
    ("digikey", "category_id", "699", "Fuentes de alimentación", 100),
    ("digikey", "category_id", "795", "Módulos", 100),
    # ---- TME category.id (stable, locale-invariant) ----
    ("tme", "category_id", "112791", "Diodos", 100),
    ("tme", "category_id", "112826", "Transistores", 100),
    ("tme", "category_id", "113637", "Microcontroladores", 100),
    ("tme", "category_id", "112866", "Microcontroladores", 100),
    ("tme", "category_id", "112576", "Sensores", 100),
    ("tme", "category_id", "113691", "Sensores", 100),
    ("tme", "category_id", "113537", "Condensadores", 100),
    ("tme", "category_id", "100300", "Resistencias", 100),
    ("tme", "category_id", "112937", "Conectores", 100),
    ("tme", "category_id", "112880", "Fuentes de alimentación", 100),
    # ---- Farnell HS tariff prefix (stable es==uk). Clean buckets only. ----
    ("farnell", "tariff_prefix", "85411", "Diodos", 70),
    ("farnell", "tariff_prefix", "85412", "Transistores", 70),
    ("farnell", "tariff_prefix", "854231", "Microcontroladores", 70),
    ("farnell", "tariff_prefix", "8532", "Condensadores", 70),
    ("farnell", "tariff_prefix", "8533", "Resistencias", 70),
    ("farnell", "tariff_prefix", "8536", "Conectores", 70),
    ("farnell", "tariff_prefix", "8473", "Módulos", 70),
    # ---- Farnell name_keyword: disambiguate the 85423990 IC bucket ----
    ("farnell", "name_keyword", "sensor", "Sensores", 40),
    ("farnell", "name_keyword", "regulador", "Fuentes de alimentación", 40),
    ("farnell", "name_keyword", "modulo", "Módulos", 40),
    ("farnell", "name_keyword", "placa", "Módulos", 40),
    # ---- Mouser name_keyword (localized ES leaf name; weakest signal) ----
    ("mouser", "name_keyword", "diodo", "Diodos", 40),
    ("mouser", "name_keyword", "mosfet", "Transistores", 40),
    ("mouser", "name_keyword", "transistor", "Transistores", 40),
    ("mouser", "name_keyword", "microcontrolador", "Microcontroladores", 40),
    ("mouser", "name_keyword", "mcu", "Microcontroladores", 40),
    ("mouser", "name_keyword", "condensador", "Condensadores", 40),
    ("mouser", "name_keyword", "mlcc", "Condensadores", 40),
    ("mouser", "name_keyword", "resistor", "Resistencias", 40),
    ("mouser", "name_keyword", "resistencia", "Resistencias", 40),
    ("mouser", "name_keyword", "conector", "Conectores", 40),
    ("mouser", "name_keyword", "cabecera", "Conectores", 40),
    ("mouser", "name_keyword", "alojamiento", "Conectores", 40),
    ("mouser", "name_keyword", "regulador", "Fuentes de alimentación", 40),
    ("mouser", "name_keyword", "ldo", "Fuentes de alimentación", 40),
    ("mouser", "name_keyword", "sensor", "Sensores", 40),
    ("mouser", "name_keyword", "modulo", "Módulos", 40),
)


def upgrade() -> None:
    conn = op.get_bind()
    stmt = sa.text(
        """
        INSERT INTO component_family_rules
            (supplier, match_type, match_value, family, confidence, priority,
             enabled, notes)
        VALUES (:supplier, :match_type, :match_value, :family, :confidence, 0,
                true, 'seed:ingest-component-from-mpn')
        ON CONFLICT (supplier, match_type, match_value) DO NOTHING
        """
    )
    for supplier, match_type, match_value, family, confidence in _SEED:
        conn.execute(
            stmt,
            {
                "supplier": supplier,
                "match_type": match_type,
                "match_value": match_value,
                "family": family,
                "confidence": confidence,
            },
        )


def downgrade() -> None:
    conn = op.get_bind()
    stmt = sa.text(
        """
        DELETE FROM component_family_rules
        WHERE supplier = :supplier
          AND match_type = :match_type
          AND match_value = :match_value
          AND notes = 'seed:ingest-component-from-mpn'
        """
    )
    for supplier, match_type, match_value, _family, _confidence in _SEED:
        conn.execute(
            stmt,
            {
                "supplier": supplier,
                "match_type": match_type,
                "match_value": match_value,
            },
        )
