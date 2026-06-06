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
from typing import Literal

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
    last_seen_at: datetime = field(
        default_factory=lambda: datetime.now(UTC),
    )
