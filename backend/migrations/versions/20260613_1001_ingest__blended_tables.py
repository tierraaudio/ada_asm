"""ingest-component-from-mpn: per-supplier blended tables + family rules.

Revision ID: 20260613_1001
Revises: 20260613_1000
Create Date: 2026-06-13 10:01:00

Creates the relational tables the ingestion pipeline populates:

- `component_parameters`: parametric specs (voltage/tolerance/package...) as
  N key/value rows per (component, supplier).
- `component_compliance`: export/customs + compliance codes (ECCN, HTS,
  RoHS, REACH, MSL) as code_type -> code_value rows.
- `component_documents`: datasheets and other documents; supports multiple
  per component, each with archival provenance (blob_path, sha256...).
- `component_cross_refs`: alternates / substitutes / aliases / packaging
  variants as ref_type -> ref_value rows.
- `component_supplier_payloads`: raw JSONB snapshot of each supplier's
  product object, so doc-only fields are re-parseable without an API call.
- `component_family_rules`: editable seed table mapping each supplier's
  category signal to one of our internal families (see family-inference).

Reversible: downgrade drops all six tables.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260613_1001"
down_revision: str | None = "20260613_1000"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


SUPPLIER_CODES = ("mouser", "digikey", "tme", "farnell", "rs")
MATCH_TYPES = ("category_id", "tariff_prefix", "name_keyword")
FAMILIES = (
    "Diodos",
    "Transistores",
    "Microcontroladores",
    "Sensores",
    "Condensadores",
    "Resistencias",
    "Conectores",
    "Fuentes de alimentación",
    "Módulos",
)


def _in_clause(values: tuple[str, ...]) -> str:
    return ", ".join("'" + v.replace("'", "''") + "'" for v in values)


def _uuid_pk() -> sa.Column:
    return sa.Column(
        "id",
        postgresql.UUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )


def _component_fk() -> sa.Column:
    return sa.Column(
        "component_id",
        postgresql.UUID(as_uuid=True),
        sa.ForeignKey("components.id", ondelete="CASCADE"),
        nullable=False,
    )


def _timestamps() -> tuple[sa.Column, ...]:
    return (
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


def upgrade() -> None:
    # ----- component_parameters -----
    op.create_table(
        "component_parameters",
        _uuid_pk(),
        _component_fk(),
        sa.Column("supplier", sa.String(length=32), nullable=False),
        sa.Column("param_key", sa.String(length=128), nullable=True),
        sa.Column("param_label", sa.String(length=255), nullable=False),
        sa.Column("param_value", sa.Text(), nullable=False),
        sa.Column("param_unit", sa.String(length=64), nullable=True),
        *_timestamps(),
        sa.CheckConstraint(
            f"supplier IN ({_in_clause(SUPPLIER_CODES)})",
            name="ck_component_parameters_supplier",
        ),
    )
    op.create_index(
        "ix_component_parameters_component",
        "component_parameters",
        ["component_id"],
    )

    # ----- component_compliance -----
    op.create_table(
        "component_compliance",
        _uuid_pk(),
        _component_fk(),
        sa.Column("supplier", sa.String(length=32), nullable=False),
        sa.Column("code_type", sa.String(length=64), nullable=False),
        sa.Column("code_value", sa.String(length=255), nullable=False),
        *_timestamps(),
        sa.CheckConstraint(
            f"supplier IN ({_in_clause(SUPPLIER_CODES)})",
            name="ck_component_compliance_supplier",
        ),
    )
    op.create_index(
        "ix_component_compliance_component",
        "component_compliance",
        ["component_id"],
    )

    # ----- component_documents -----
    op.create_table(
        "component_documents",
        _uuid_pk(),
        _component_fk(),
        sa.Column("supplier", sa.String(length=32), nullable=True),
        sa.Column("doc_type", sa.String(length=32), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("file_name", sa.String(length=512), nullable=True),
        sa.Column("size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("language", sa.String(length=16), nullable=True),
        sa.Column("blob_path", sa.Text(), nullable=True),
        sa.Column("sha256", sa.String(length=64), nullable=True),
        sa.Column("content_type", sa.String(length=128), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
    )
    op.create_index(
        "ix_component_documents_component",
        "component_documents",
        ["component_id"],
    )
    op.create_index(
        "ix_component_documents_sha256",
        "component_documents",
        ["sha256"],
    )

    # ----- component_cross_refs -----
    op.create_table(
        "component_cross_refs",
        _uuid_pk(),
        _component_fk(),
        sa.Column("supplier", sa.String(length=32), nullable=False),
        sa.Column("ref_type", sa.String(length=32), nullable=False),
        sa.Column("ref_value", sa.String(length=255), nullable=False),
        *_timestamps(),
        sa.CheckConstraint(
            f"supplier IN ({_in_clause(SUPPLIER_CODES)})",
            name="ck_component_cross_refs_supplier",
        ),
    )
    op.create_index(
        "ix_component_cross_refs_component",
        "component_cross_refs",
        ["component_id"],
    )

    # ----- component_supplier_payloads -----
    op.create_table(
        "component_supplier_payloads",
        _uuid_pk(),
        _component_fk(),
        sa.Column("supplier", sa.String(length=32), nullable=False),
        sa.Column("raw_payload", postgresql.JSONB(), nullable=False),
        sa.Column(
            "fetched_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        *_timestamps(),
        sa.CheckConstraint(
            f"supplier IN ({_in_clause(SUPPLIER_CODES)})",
            name="ck_component_supplier_payloads_supplier",
        ),
        sa.UniqueConstraint(
            "component_id",
            "supplier",
            name="uq_component_supplier_payloads_component_supplier",
        ),
    )

    # ----- component_family_rules -----
    op.create_table(
        "component_family_rules",
        _uuid_pk(),
        sa.Column("supplier", sa.String(length=32), nullable=False),
        sa.Column("match_type", sa.String(length=32), nullable=False),
        sa.Column("match_value", sa.String(length=255), nullable=False),
        sa.Column("family", sa.String(length=64), nullable=False),
        sa.Column(
            "confidence",
            sa.SmallInteger(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "priority",
            sa.SmallInteger(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        *_timestamps(),
        sa.CheckConstraint(
            f"supplier IN ({_in_clause(SUPPLIER_CODES)})",
            name="ck_component_family_rules_supplier",
        ),
        sa.CheckConstraint(
            f"match_type IN ({_in_clause(MATCH_TYPES)})",
            name="ck_component_family_rules_match_type",
        ),
        sa.CheckConstraint(
            f"family IN ({_in_clause(FAMILIES)})",
            name="ck_component_family_rules_family",
        ),
        sa.UniqueConstraint(
            "supplier",
            "match_type",
            "match_value",
            name="uq_component_family_rules_supplier_type_value",
        ),
    )
    op.create_index(
        "ix_component_family_rules_lookup",
        "component_family_rules",
        ["supplier", "match_type", "match_value"],
    )


def downgrade() -> None:
    op.drop_table("component_family_rules")
    op.drop_table("component_supplier_payloads")
    op.drop_index(
        "ix_component_cross_refs_component", table_name="component_cross_refs"
    )
    op.drop_table("component_cross_refs")
    op.drop_index(
        "ix_component_documents_sha256", table_name="component_documents"
    )
    op.drop_index(
        "ix_component_documents_component", table_name="component_documents"
    )
    op.drop_table("component_documents")
    op.drop_index(
        "ix_component_compliance_component", table_name="component_compliance"
    )
    op.drop_table("component_compliance")
    op.drop_index(
        "ix_component_parameters_component", table_name="component_parameters"
    )
    op.drop_table("component_parameters")
