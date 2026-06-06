"""Mouser Search API adapter.

Endpoint: `POST https://api.mouser.com/api/v2/search/partnumber?apiKey=...`
Body: `{"SearchByPartRequest": {"mouserPartNumber": "<MPN>", "partSearchOptions": ""}}`

Despite the field name `mouserPartNumber`, the endpoint matches by
manufacturer part number (MPN) too — that's the documented behaviour and
what we rely on. The supplier's own SKU is captured separately in
`MouserPartNumber` on the response and stored as `supplier_sku`.

Errors:
- Invalid API key: HTTP 200 with `Errors[0].ResourceKey == "InvalidApiKey"`
  → `SupplierAuthError`.
- HTTP 5xx → `SupplierTransportError`.
- Timeout → `SupplierTimeoutError`.
- Non-JSON / unexpected shape → `SupplierParseError`.
- No match: HTTP 200 with `SearchResults.NumberOfResult == 0` → return None.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx

from app.core.exceptions import (
    SupplierAuthError,
    SupplierParseError,
    SupplierTimeoutError,
    SupplierTransportError,
)
from app.domain.entities.supplier_quote import (
    SupplierCode,
    SupplierPriceBreak,
    SupplierQuote,
)
from app.infrastructure import fx, rate_limit

_ENDPOINT = "https://api.mouser.com/api/v2/search/partnumber"
_HTTP_TIMEOUT_SECONDS = 10.0
_RATE_LIMIT_PER_MINUTE = 30
_BUCKET = "supplier:mouser"

# Mouser may return prices as "$3.50", "3,50 €", "£2.10", "3.50", etc. We
# extract the first decimal-looking token and rely on the explicit
# `Currency` ISO 4217 field for the currency code.
_PRICE_NUMERIC_RE = re.compile(r"[-+]?[0-9]*[\.,]?[0-9]+")


class MouserAdapter:
    """`SupplierAdapter` for Mouser Electronics Search API."""

    code: SupplierCode = "mouser"

    def __init__(self, *, api_key: str) -> None:
        self._api_key = api_key

    async def fetch_by_mpn(self, mpn: str) -> SupplierQuote | None:
        await rate_limit.acquire(_BUCKET, _RATE_LIMIT_PER_MINUTE)

        payload = {
            "SearchByPartRequest": {
                "mouserPartNumber": mpn,
                "partSearchOptions": "",
            }
        }
        params = {"apiKey": self._api_key}

        try:
            async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT_SECONDS) as client:
                response = await client.post(_ENDPOINT, params=params, json=payload)
        except httpx.TimeoutException as exc:
            raise SupplierTimeoutError(f"Mouser timed out: {exc}") from exc
        except httpx.HTTPError as exc:
            raise SupplierTransportError(f"Mouser HTTP error: {exc}") from exc

        if response.status_code >= 500:
            raise SupplierTransportError(
                f"Mouser HTTP {response.status_code}",
            )
        if response.status_code in (401, 403):
            raise SupplierAuthError(
                f"Mouser HTTP {response.status_code} on auth",
            )
        if response.status_code != 200:
            raise SupplierTransportError(
                f"Mouser HTTP {response.status_code}",
            )

        try:
            body = response.json()
        except json.JSONDecodeError as exc:
            raise SupplierParseError(f"Mouser non-JSON response: {exc}") from exc

        # Mouser reports a bad key as HTTP 200 with an Errors entry; promote
        # to a typed auth error so the caller's behaviour matches a real 401.
        for err in body.get("Errors") or []:
            if err.get("ResourceKey") == "InvalidApiKey":
                raise SupplierAuthError("Mouser rejected API key")

        results = body.get("SearchResults") or {}
        parts = results.get("Parts") or []
        if not parts:
            return None

        try:
            return await _build_quote(parts[0], mpn=mpn)
        except (KeyError, TypeError, InvalidOperation) as exc:
            raise SupplierParseError(f"Mouser response shape: {exc}") from exc


def _parse_price(raw: str) -> Decimal:
    match = _PRICE_NUMERIC_RE.search(raw)
    if not match:
        raise SupplierParseError(f"Mouser price unparseable: {raw!r}")
    token = match.group(0).replace(",", ".")
    return Decimal(token)


async def _build_quote(part: dict[str, Any], *, mpn: str) -> SupplierQuote:
    raw_breaks = part.get("PriceBreaks") or []
    breaks: list[SupplierPriceBreak] = []
    for raw_break in raw_breaks:
        currency_original = (raw_break.get("Currency") or "USD").upper()
        price_original = _parse_price(str(raw_break.get("Price") or "0"))
        try:
            price_eur = await fx.to_eur(price_original, currency_original)
        except Exception:  # noqa: BLE001 - any FX failure → keep original, drop EUR
            price_eur = None
        breaks.append(
            SupplierPriceBreak(
                quantity=int(raw_break.get("Quantity") or 0),
                price_original=price_original,
                currency_original=currency_original,
                price_eur=price_eur,
            )
        )

    stock_raw = part.get("AvailabilityInStock")
    try:
        stock = int(stock_raw) if stock_raw is not None else None
    except (TypeError, ValueError):
        stock = None

    # Use the supplier's reported manufacturer part number when present so we
    # round-trip the canonical MPN; fall back to the lookup MPN otherwise.
    resolved_mpn = (part.get("ManufacturerPartNumber") or mpn).strip() or mpn

    return SupplierQuote(
        supplier="mouser",
        mpn=resolved_mpn,
        manufacturer=part.get("Manufacturer"),
        name=part.get("Description"),
        description=part.get("Description"),
        family_hint=part.get("Category"),
        datasheet_url=part.get("DataSheetUrl"),
        package=None,  # Mouser exposes packaging under ProductAttributes; out of scope
        stock=stock,
        price_breaks=tuple(breaks),
        supplier_sku=part.get("MouserPartNumber"),
        supplier_product_url=part.get("ProductDetailUrl"),
        last_seen_at=datetime.now(timezone.utc),
    )
