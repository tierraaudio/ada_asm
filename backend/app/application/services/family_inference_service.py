"""Infer the internal family from heterogeneous supplier category signals.

Our nine internal families ARE the canonical taxonomy; each supplier's
native category signal is translated INTO it via `component_family_rules`.
Resolution is by SIGNAL STRENGTH (stable category_id > HS tariff > localized
name keyword), NOT by the presentation merge priority — that order would let
Mouser's weak localized name beat DigiKey's stable id. See change
`ingest-component-from-mpn` (family-inference) and the research design doc.
"""

from __future__ import annotations

import logging
import unicodedata
from dataclasses import dataclass

from app.domain.entities.component_family_rule import ComponentFamilyRule
from app.domain.entities.supplier_quote import SupplierQuote

_log = logging.getLogger(__name__)

# Supplier evaluation order = signal-strength order, NOT presentation order.
_SUPPLIER_PRIORITY = ("digikey", "tme", "farnell", "mouser")

# Family → internal SKU prefix (matches the seed-script convention).
_FAMILY_SKU_PREFIX: dict[str, str] = {
    "Diodos": "DIO",
    "Transistores": "TRN",
    "Microcontroladores": "MCU",
    "Sensores": "SEN",
    "Condensadores": "CAP",
    "Resistencias": "RES",
    "Conectores": "CON",
    "Fuentes de alimentación": "PWR",
    "Módulos": "MOD",
}
_GENERIC_SKU_PREFIX = "CMP"


def normalize_keyword(text: str) -> str:
    """NFKD-normalize, strip accents, lowercase — for robust substring match."""

    decomposed = unicodedata.normalize("NFKD", text)
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    return stripped.casefold().strip()


def sku_prefix_for_family(family: str | None) -> str:
    """Return the SKU prefix for a family (generic when unknown/empty)."""

    if not family:
        return _GENERIC_SKU_PREFIX
    return _FAMILY_SKU_PREFIX.get(family, _GENERIC_SKU_PREFIX)


@dataclass(frozen=True)
class FamilyInferenceResult:
    family: str | None
    needs_review: bool
    inferred_supplier: str | None = None
    match_type: str | None = None
    raw_category_id: str | None = None
    raw_category_name: str | None = None
    raw_tariff_code: str | None = None
    confidence: int | None = None


def _match_quote(
    quote: SupplierQuote,
    rules_by_supplier: dict[str, list[ComponentFamilyRule]],
) -> tuple[ComponentFamilyRule, str | None, str | None, str | None] | None:
    """Best rule match for one quote, or None.

    Returns `(rule, raw_category_id, raw_category_name, raw_tariff_code)`.
    Within a supplier, evaluates category_id, then tariff_prefix (longest
    prefix wins), then name_keyword.
    """

    rules = rules_by_supplier.get(quote.supplier) or []
    if not rules:
        return None

    # 1. category_id (exact).
    if quote.supplier_category_id:
        for rule in rules:
            if rule.match_type == "category_id" and rule.match_value == quote.supplier_category_id:
                return rule, quote.supplier_category_id, quote.supplier_category_name, None

    # 2. tariff_prefix (longest matching prefix).
    if quote.tariff_code:
        prefix_rules = [
            r
            for r in rules
            if r.match_type == "tariff_prefix" and quote.tariff_code.startswith(r.match_value)
        ]
        if prefix_rules:
            rule = max(prefix_rules, key=lambda r: len(r.match_value))
            return rule, None, quote.supplier_category_name, quote.tariff_code

    # 3. name_keyword (normalized substring).
    if quote.supplier_category_name:
        haystack = normalize_keyword(quote.supplier_category_name)
        for rule in rules:
            if rule.match_type == "name_keyword" and rule.match_value in haystack:
                return rule, None, quote.supplier_category_name, quote.tariff_code

    return None


def resolve_family(
    quotes: list[SupplierQuote],
    rules: list[ComponentFamilyRule],
) -> FamilyInferenceResult:
    """Resolve a single family from all responding suppliers' signals.

    Walks suppliers in signal-strength order and returns the first confident
    match. Leaves the family empty (`needs_review=True`) when nothing maps,
    logging each unmapped signal so the rules table can be grown.
    """

    enabled = [r for r in rules if r.enabled]
    rules_by_supplier: dict[str, list[ComponentFamilyRule]] = {}
    for rule in enabled:
        rules_by_supplier.setdefault(rule.supplier, []).append(rule)

    quotes_by_supplier: dict[str, SupplierQuote] = {q.supplier: q for q in quotes}

    for supplier in _SUPPLIER_PRIORITY:
        quote = quotes_by_supplier.get(supplier)
        if quote is None:
            continue
        match = _match_quote(quote, rules_by_supplier)
        if match is not None:
            rule, raw_id, raw_name, raw_tariff = match
            return FamilyInferenceResult(
                family=rule.family,
                needs_review=False,
                inferred_supplier=supplier,
                match_type=rule.match_type,
                raw_category_id=raw_id,
                raw_category_name=raw_name,
                raw_tariff_code=raw_tariff,
                confidence=rule.confidence,
            )

    # No confident match — log every signal so the table can grow.
    for quote in quotes:
        _log.info(
            "family_inference.unmapped supplier=%s category_id=%s category_name=%s tariff=%s",
            quote.supplier,
            quote.supplier_category_id,
            quote.supplier_category_name,
            quote.tariff_code,
        )
    return FamilyInferenceResult(family=None, needs_review=True)
