"""Domain value objects for a supplier's quote on a single component.

A `SupplierQuote` is the normalised return type of every `SupplierAdapter`:
identical shape regardless of whether the underlying API is Mouser, DigiKey,
TME, Farnell, or RS. The component lookup endpoint merges a list of these
progressively; the daily sync task upserts each into the append-only
`supplier_prices` / `supplier_stocks` history.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Literal

SupplierCode = Literal["mouser", "digikey", "tme", "farnell", "rs"]


@dataclass(frozen=True)
class SupplierPriceBreak:
    """One quantity-tier entry from a supplier's price ladder.

    `price_eur` is the converted value (using the daily-cached ECB rate);
    `price_original` and `currency_original` preserve the supplier's native
    quote so prices can be re-converted if EUR rates are revised.
    """

    quantity: int
    price_original: Decimal
    currency_original: str  # ISO 4217, e.g. "USD"
    price_eur: Decimal | None = None


@dataclass(frozen=True)
class SupplierParameter:
    """One parametric attribute (a spec row) from a supplier.

    `key` is the supplier's stable parameter id when it exposes one
    (DigiKey `ParameterId`, TME parameter id); `label` is the human name
    (often localized); `unit` is split out when the supplier provides it.
    """

    label: str
    value: str
    key: str | None = None
    unit: str | None = None


@dataclass(frozen=True)
class SupplierComplianceCode:
    """One compliance / export-control code (ECCN, HTS, RoHS, REACH, MSL...)."""

    code_type: str
    code_value: str


@dataclass(frozen=True)
class SupplierQuote:
    """Normalised payload from one supplier for one MPN.

    Fields are nullable because no single supplier returns the full set; the
    lookup endpoint merges fields progressively. The MPN preserved on this
    record is the one resolved from the supplier's MPN field (Mouser's
    `ManufacturerPartNumber`, TME's `OriginalSymbol`, etc.) — NOT the
    supplier's own SKU, which is captured separately in `supplier_sku`.
    """

    supplier: SupplierCode
    mpn: str
    manufacturer: str | None = None
    name: str | None = None
    description: str | None = None
    family_hint: str | None = None
    datasheet_url: str | None = None
    package: str | None = None
    stock: int | None = None
    price_breaks: tuple[SupplierPriceBreak, ...] = field(default_factory=tuple)
    supplier_sku: str | None = None
    supplier_product_url: str | None = None
    # --- Category signal for family inference (change `ingest-component-from-mpn`).
    # Raw per-supplier signals — NOT merged by presentation priority. ---
    supplier_category_id: str | None = None
    supplier_category_name: str | None = None
    tariff_code: str | None = None
    # --- Blended extra data (change `ingest-component-from-mpn`) ---
    image_url: str | None = None
    lifecycle_status: str | None = None
    country_of_origin: str | None = None
    moq: int | None = None
    order_multiple: int | None = None
    lead_time_days: int | None = None
    unit_weight_kg: Decimal | None = None
    parameters: tuple[SupplierParameter, ...] = field(default_factory=tuple)
    compliance: tuple[SupplierComplianceCode, ...] = field(default_factory=tuple)
    # Raw supplier product object, preserved for re-parsing without a new
    # API call (doc-only fields not promoted to columns).
    raw_payload: dict[str, Any] | None = None
    last_seen_at: datetime = field(
        default_factory=lambda: datetime.now(UTC),
    )
