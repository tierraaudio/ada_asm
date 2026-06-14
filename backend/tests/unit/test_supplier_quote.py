"""Unit tests for the enriched SupplierQuote value object.

Covers the blended fields + the new SupplierParameter / SupplierComplianceCode
value objects added by change `ingest-component-from-mpn`.
"""

from __future__ import annotations

from decimal import Decimal

from app.domain.entities.supplier_quote import (
    SupplierComplianceCode,
    SupplierParameter,
    SupplierPriceBreak,
    SupplierQuote,
)


def test_supplier_parameter_holds_key_label_value_unit() -> None:
    param = SupplierParameter(
        key="ParameterId-12", label="Voltage - Supply", value="4.5 V ~ 16 V", unit="V"
    )
    assert param.key == "ParameterId-12"
    assert param.label == "Voltage - Supply"
    assert param.value == "4.5 V ~ 16 V"
    assert param.unit == "V"


def test_supplier_parameter_key_and_unit_optional() -> None:
    param = SupplierParameter(label="Mounting Type", value="Surface Mount")
    assert param.key is None
    assert param.unit is None


def test_supplier_compliance_code_holds_type_and_value() -> None:
    code = SupplierComplianceCode(code_type="ECCN", code_value="EAR99")
    assert code.code_type == "ECCN"
    assert code.code_value == "EAR99"


def test_supplier_quote_defaults_new_fields_to_none_or_empty() -> None:
    quote = SupplierQuote(supplier="mouser", mpn="NE555P")
    assert quote.supplier_category_id is None
    assert quote.supplier_category_name is None
    assert quote.tariff_code is None
    assert quote.image_url is None
    assert quote.lifecycle_status is None
    assert quote.moq is None
    assert quote.order_multiple is None
    assert quote.lead_time_days is None
    assert quote.parameters == ()
    assert quote.compliance == ()
    assert quote.raw_payload is None


def test_supplier_quote_carries_blended_payload() -> None:
    quote = SupplierQuote(
        supplier="digikey",
        mpn="NE555P",
        supplier_category_id="280",
        supplier_category_name="Single Diodes",
        tariff_code="85411000",
        image_url="https://mm.digikey.com/photo.jpg",
        lifecycle_status="Active",
        moq=1,
        order_multiple=1,
        lead_time_days=42,
        unit_weight_kg=Decimal("0.0002"),
        parameters=(SupplierParameter(label="Voltage", value="16V"),),
        compliance=(SupplierComplianceCode(code_type="RoHS", code_value="Compliant"),),
        price_breaks=(
            SupplierPriceBreak(quantity=1, price_original=Decimal("0.5"), currency_original="EUR"),
        ),
        raw_payload={"ManufacturerProductNumber": "NE555P"},
    )
    assert quote.supplier_category_id == "280"
    assert quote.parameters[0].label == "Voltage"
    assert quote.compliance[0].code_type == "RoHS"
    assert quote.raw_payload == {"ManufacturerProductNumber": "NE555P"}
