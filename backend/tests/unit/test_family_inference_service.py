"""Unit tests for FamilyInferenceService.

Pure logic over an in-memory rule set mirroring the seeded
`component_family_rules`. Covers the nine families, signal-strength
resolution, the BME280 conflict, no-match review, and SKU prefixes.
"""

from __future__ import annotations

from app.application.services.family_inference_service import (
    normalize_keyword,
    resolve_family,
    sku_prefix_for_family,
)
from app.domain.entities.component_family_rule import ComponentFamilyRule
from app.domain.entities.supplier_quote import SupplierQuote

# A subset of the seeded rules, enough to exercise the resolver.
_RULES = [
    ComponentFamilyRule("digikey", "category_id", "280", "Diodos", confidence=100),
    ComponentFamilyRule("digikey", "category_id", "278", "Transistores", confidence=100),
    ComponentFamilyRule("digikey", "category_id", "795", "Módulos", confidence=100),
    ComponentFamilyRule("tme", "category_id", "113691", "Sensores", confidence=100),
    ComponentFamilyRule("farnell", "tariff_prefix", "85411", "Diodos", confidence=70),
    ComponentFamilyRule("farnell", "tariff_prefix", "8536", "Conectores", confidence=70),
    ComponentFamilyRule("farnell", "name_keyword", "sensor", "Sensores", confidence=40),
    ComponentFamilyRule("mouser", "name_keyword", "diodo", "Diodos", confidence=40),
    ComponentFamilyRule(
        "mouser", "name_keyword", "condensador", "Condensadores", confidence=40
    ),
]


def _q(supplier, **kw) -> SupplierQuote:
    return SupplierQuote(supplier=supplier, mpn="X", **kw)


def test_normalize_keyword_strips_accents_and_case() -> None:
    assert normalize_keyword("Condensadores de CERÁMICA") == "condensadores de ceramica"


def test_resolves_from_digikey_category_id() -> None:
    result = resolve_family([_q("digikey", supplier_category_id="280")], _RULES)
    assert result.family == "Diodos"
    assert result.needs_review is False
    assert result.inferred_supplier == "digikey"
    assert result.match_type == "category_id"
    assert result.raw_category_id == "280"
    assert result.confidence == 100


def test_signal_strength_digikey_beats_mouser_keyword() -> None:
    # Mouser keyword would say Diodos; DigiKey stable id says Transistores.
    quotes = [
        _q("mouser", supplier_category_name="Diodo de conmutación"),
        _q("digikey", supplier_category_id="278"),
    ]
    result = resolve_family(quotes, _RULES)
    assert result.family == "Transistores"
    assert result.inferred_supplier == "digikey"


def test_falls_back_to_mouser_keyword_when_higher_signals_silent() -> None:
    result = resolve_family(
        [_q("mouser", supplier_category_name="Condensadores MLCC")], _RULES
    )
    assert result.family == "Condensadores"
    assert result.match_type == "name_keyword"


def test_farnell_tariff_prefix_longest_wins() -> None:
    result = resolve_family([_q("farnell", tariff_code="85411000")], _RULES)
    assert result.family == "Diodos"
    assert result.raw_tariff_code == "85411000"


def test_bme280_conflict_digikey_module_wins_over_tme_sensor() -> None:
    # The breakout-board case: DigiKey files it under Módulos, TME under
    # Sensores. Signal-strength order makes DigiKey the arbiter.
    quotes = [
        _q("tme", supplier_category_id="113691"),
        _q("digikey", supplier_category_id="795"),
    ]
    result = resolve_family(quotes, _RULES)
    assert result.family == "Módulos"
    assert result.inferred_supplier == "digikey"


def test_no_match_flags_for_review() -> None:
    result = resolve_family(
        [_q("digikey", supplier_category_id="999999")], _RULES
    )
    assert result.family is None
    assert result.needs_review is True
    assert result.inferred_supplier is None


def test_disabled_rules_are_ignored() -> None:
    rules = [
        ComponentFamilyRule(
            "digikey", "category_id", "280", "Diodos", confidence=100, enabled=False
        )
    ]
    result = resolve_family([_q("digikey", supplier_category_id="280")], rules)
    assert result.family is None
    assert result.needs_review is True


def test_sku_prefix_per_family() -> None:
    assert sku_prefix_for_family("Diodos") == "DIO"
    assert sku_prefix_for_family("Microcontroladores") == "MCU"
    assert sku_prefix_for_family("Fuentes de alimentación") == "PWR"
    assert sku_prefix_for_family(None) == "CMP"
    assert sku_prefix_for_family("Familia Inventada") == "CMP"
