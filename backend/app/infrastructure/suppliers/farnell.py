"""element14 / Farnell Product Search API adapter (Basic tier).

Endpoint:
    `GET https://api.element14.com/catalog/products?term=any:<MPN>&...`

Auth: API key in query string (`callInfo.apiKey=<key>`). No signature,
no OAuth, no callback.

Store: `FARNELL_STORE_ID` controls regional pricing and currency. We
default to `es.farnell.com` which returns EUR prices natively — FX is an
identity conversion. If a UK store (`uk.farnell.com`) is ever
configured, currency would be GBP and the FX helper would do the real
conversion.

Rate limit (Basic tier): 2 calls/sec, 1000/day. We cap our bucket at 100
calls/min to stay safely under the 2/sec ceiling while leaving headroom
for bursts.

MPN matching:
- Query: `term=any:<MPN>` does a free-text match.
- Resolve: the response's `products[].translatedManufacturerPartNumber`
  is the manufacturer's MPN; pick the candidate that matches the queried
  MPN case-insensitively, falling back to the first result.
"""

from __future__ import annotations

import json
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

_ENDPOINT = "https://api.element14.com/catalog/products"
_HTTP_TIMEOUT_SECONDS = 10.0
_RATE_LIMIT_PER_MINUTE = 100
_BUCKET = "supplier:farnell"


def _currency_for_store(store_id: str) -> str:
    """Best-effort mapping from a Farnell store host to ISO 4217.

    Used so the returned `SupplierPriceBreak.currency_original` reflects
    what the API actually quoted, even though Farnell does not return an
    explicit currency code on each price break.
    """

    store = (store_id or "").lower()
    if ".farnell.com" in store and (
        store.startswith("uk.") or store.startswith("ie.")
    ):
        return "GBP"
    if "newark.com" in store:
        return "USD"
    # Default for es/de/fr/it/at/be/nl/pt/etc. — Eurozone storefronts.
    return "EUR"


class FarnellAdapter:
    """`SupplierAdapter` for element14 / Farnell Product Search API."""

    code: SupplierCode = "farnell"

    def __init__(self, *, api_key: str, store_id: str) -> None:
        self._api_key = api_key
        self._store_id = store_id
        self._currency = _currency_for_store(store_id)

    async def fetch_by_mpn(self, mpn: str) -> SupplierQuote | None:
        await rate_limit.acquire(_BUCKET, _RATE_LIMIT_PER_MINUTE)

        params: dict[str, str] = {
            "term": f"any:{mpn}",
            "storeInfo.id": self._store_id,
            "resultsSettings.offset": "0",
            "resultsSettings.numberOfResults": "5",
            "resultsSettings.responseGroup": "large",
            "callInfo.omitXmlSchema": "false",
            "callInfo.responseDataFormat": "json",
            "callInfo.apiKey": self._api_key,
        }

        try:
            async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT_SECONDS) as client:
                response = await client.get(_ENDPOINT, params=params)
        except httpx.TimeoutException as exc:
            raise SupplierTimeoutError(f"Farnell timed out: {exc}") from exc
        except httpx.HTTPError as exc:
            raise SupplierTransportError(f"Farnell HTTP error: {exc}") from exc

        if response.status_code >= 500:
            raise SupplierTransportError(f"Farnell HTTP {response.status_code}")
        if response.status_code in (401, 403):
            raise SupplierAuthError(f"Farnell HTTP {response.status_code} on auth")
        if response.status_code != 200:
            raise SupplierTransportError(f"Farnell HTTP {response.status_code}")

        try:
            body = response.json()
        except json.JSONDecodeError as exc:
            raise SupplierParseError(f"Farnell non-JSON response: {exc}") from exc

        # Farnell signals "bad key" as HTTP 200 with an empty result, but
        # also can return an explicit "Fault" envelope under certain
        # conditions. Promote either form to a typed auth error so the
        # caller distinguishes "MPN not found" from "key rejected".
        fault = body.get("Fault") or body.get("fault")
        if fault:
            detail = str(fault).lower()
            if "apikey" in detail or "key" in detail or "auth" in detail:
                raise SupplierAuthError(f"Farnell fault: {fault}")
            raise SupplierTransportError(f"Farnell fault: {fault}")

        ksr = body.get("keywordSearchReturn") or {}
        products = ksr.get("products") or []
        if not products:
            return None

        try:
            return await _build_quote(
                products,
                lookup_mpn=mpn,
                store_id=self._store_id,
                currency=self._currency,
            )
        except (KeyError, TypeError, InvalidOperation) as exc:
            raise SupplierParseError(f"Farnell response shape: {exc}") from exc


def _pick_product(products: list[dict[str, Any]], lookup_mpn: str) -> dict[str, Any]:
    """Choose the product whose `translatedManufacturerPartNumber` matches
    the queried MPN (case-insensitive, trimmed). Fall back to the first
    candidate when no exact match is present — better partial data than
    a 404 to the caller."""

    target = lookup_mpn.strip().upper()
    for p in products:
        raw = str(p.get("translatedManufacturerPartNumber") or "").strip().upper()
        if raw == target:
            return p
    return products[0]


def _construct_product_url(sku: str | None, store_id: str) -> str | None:
    """Build a best-effort Farnell product URL.

    The Search API does not return a canonical product page URL on the
    `large` response group. We synthesise one using the public store
    pattern `https://<store>/...sku/dp/<sku>`. If the SKU is missing we
    return None so the FE can decide whether to render a link.
    """

    if not sku:
        return None
    return f"https://{store_id}/_/dp/{sku}"


async def _build_quote(
    products: list[dict[str, Any]],
    *,
    lookup_mpn: str,
    store_id: str,
    currency: str,
) -> SupplierQuote:
    product = _pick_product(products, lookup_mpn)

    raw_breaks = product.get("prices") or []
    breaks: list[SupplierPriceBreak] = []
    for entry in raw_breaks:
        price = entry.get("cost")
        qty_from = entry.get("from")
        if price is None or qty_from is None:
            continue
        try:
            quantity = int(qty_from)
            price_original = Decimal(str(price))
        except (TypeError, ValueError):
            continue
        try:
            price_eur = await fx.to_eur(price_original, currency)
        except Exception:  # noqa: BLE001 — keep break, drop EUR conversion
            price_eur = None
        breaks.append(
            SupplierPriceBreak(
                quantity=quantity,
                price_original=price_original,
                currency_original=currency,
                price_eur=price_eur,
            )
        )

    stock_node = product.get("stock") or {}
    stock_raw: Any = stock_node.get("level")
    if stock_raw is None:
        stock_raw = product.get("inv")
    try:
        stock = int(stock_raw) if stock_raw is not None else None
    except (TypeError, ValueError):
        stock = None

    resolved_mpn = (
        str(product.get("translatedManufacturerPartNumber") or "").strip()
        or lookup_mpn
    )
    sku = str(product.get("sku")) if product.get("sku") is not None else None

    return SupplierQuote(
        supplier="farnell",
        mpn=resolved_mpn,
        manufacturer=product.get("brandName") or product.get("vendorName"),
        name=product.get("displayName"),
        description=product.get("displayName"),
        family_hint=None,
        # The Basic/Large response group does not include datasheet URLs.
        # Upgrading to `inventory` or `attributes` response groups exposes
        # them but doubles the payload size — defer until needed.
        datasheet_url=None,
        package=None,
        stock=stock,
        price_breaks=tuple(breaks),
        supplier_sku=sku,
        supplier_product_url=_construct_product_url(sku, store_id),
        last_seen_at=datetime.now(timezone.utc),
    )
