"""DigiKey Product Information V4 (KeywordSearch) adapter.

Auth: OAuth2 client_credentials. POST to `/v1/oauth2/token` with form
`grant_type=client_credentials&client_id=...&client_secret=...` returns a
Bearer access token valid ~600s. Cached in-process with 30s headroom.

Search: `POST https://api.digikey.com/products/v4/search/keyword`
- Body: `{"Keywords": "<MPN>", "Limit": 5, "Offset": 0}`
- Required headers:
  - `Authorization: Bearer <token>`
  - `X-DIGIKEY-Client-Id: <client_id>`
  - `X-DIGIKEY-Locale-Site: ES`
  - `X-DIGIKEY-Locale-Language: en`
  - `X-DIGIKEY-Locale-Currency: EUR`  (drives the prices currency)

Response shape (V4):
- `Products[]` — list, each with:
  - `ManufacturerProductNumber` (the MPN)
  - `Manufacturer.Name`
  - `Description.ProductDescription` + `DetailedDescription`
  - `Category.Name`
  - `DatasheetUrl`, `ProductUrl`, `PhotoUrl`
  - `QuantityAvailable` (int)
  - `ProductVariations[]` — per packaging variant, contains
    `StandardPricing[]` with `{BreakQuantity, UnitPrice, TotalPrice}` and
    `DigiKeyProductNumber` (the supplier SKU per package type).

Rate-limit: DigiKey caps the standard tier at 1000 req/day; we keep our
bucket at 60 req/min which is well within their (un-documented) per-
minute ceiling and won't burst.
"""

from __future__ import annotations

import json
import time
from datetime import UTC, datetime
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

_SEARCH_URL = "https://api.digikey.com/products/v4/search/keyword"
_HTTP_TIMEOUT_SECONDS = 12.0
_RATE_LIMIT_PER_MINUTE = 60
_BUCKET = "supplier:digikey"

_LOCALE_SITE = "ES"
_LOCALE_LANGUAGE = "en"
_LOCALE_CURRENCY = "EUR"

# In-process token cache, keyed by (client_id, client_secret) so two
# adapters with different credentials don't trample each other.
_token_cache: dict[tuple[str, str], tuple[str, float]] = {}


class DigiKeyAdapter:
    """`SupplierAdapter` for DigiKey Product Information V4."""

    code: SupplierCode = "digikey"

    def __init__(
        self,
        *,
        client_id: str,
        client_secret: str,
        token_url: str,
    ) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._token_url = token_url

    async def _get_access_token(self) -> str:
        cache_key = (self._client_id, self._client_secret)
        cached = _token_cache.get(cache_key)
        if cached is not None:
            value, expires_at = cached
            if time.time() < expires_at:
                return value

        try:
            async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT_SECONDS) as client:
                response = await client.post(
                    self._token_url,
                    data={
                        "grant_type": "client_credentials",
                        "client_id": self._client_id,
                        "client_secret": self._client_secret,
                    },
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )
        except httpx.TimeoutException as exc:
            raise SupplierTimeoutError(f"DigiKey auth timed out: {exc}") from exc
        except httpx.HTTPError as exc:
            raise SupplierTransportError(f"DigiKey auth HTTP error: {exc}") from exc

        if response.status_code in (400, 401, 403):
            raise SupplierAuthError(
                f"DigiKey auth rejected credentials (HTTP {response.status_code})",
            )
        if response.status_code != 200:
            raise SupplierTransportError(
                f"DigiKey auth HTTP {response.status_code}",
            )

        try:
            payload = response.json()
            access_token = payload["access_token"]
            expires_in = int(payload.get("expires_in", 600))
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            raise SupplierParseError(f"DigiKey auth response shape: {exc}") from exc

        _token_cache[cache_key] = (access_token, time.time() + expires_in - 30)
        return access_token

    async def fetch_by_mpn(self, mpn: str) -> SupplierQuote | None:
        await rate_limit.acquire(_BUCKET, _RATE_LIMIT_PER_MINUTE)
        access_token = await self._get_access_token()

        headers = {
            "Authorization": f"Bearer {access_token}",
            "X-DIGIKEY-Client-Id": self._client_id,
            "X-DIGIKEY-Locale-Site": _LOCALE_SITE,
            "X-DIGIKEY-Locale-Language": _LOCALE_LANGUAGE,
            "X-DIGIKEY-Locale-Currency": _LOCALE_CURRENCY,
            "Content-Type": "application/json",
        }
        body = {"Keywords": mpn, "Limit": 5, "Offset": 0}

        try:
            async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT_SECONDS) as client:
                response = await client.post(_SEARCH_URL, json=body, headers=headers)
        except httpx.TimeoutException as exc:
            raise SupplierTimeoutError(f"DigiKey timed out: {exc}") from exc
        except httpx.HTTPError as exc:
            raise SupplierTransportError(f"DigiKey HTTP error: {exc}") from exc

        if response.status_code >= 500:
            raise SupplierTransportError(f"DigiKey HTTP {response.status_code}")
        if response.status_code in (401, 403):
            raise SupplierAuthError(f"DigiKey HTTP {response.status_code} on auth")
        if response.status_code == 429:
            from app.core.exceptions import SupplierRateLimitedError

            raise SupplierRateLimitedError("DigiKey HTTP 429 — daily quota exhausted")
        if response.status_code != 200:
            raise SupplierTransportError(f"DigiKey HTTP {response.status_code}")

        try:
            payload = response.json()
        except json.JSONDecodeError as exc:
            raise SupplierParseError(f"DigiKey non-JSON response: {exc}") from exc

        products = payload.get("Products") or []
        if not products:
            return None

        try:
            return await _build_quote(products, lookup_mpn=mpn)
        except (KeyError, TypeError, InvalidOperation) as exc:
            raise SupplierParseError(f"DigiKey response shape: {exc}") from exc


def _pick_product(products: list[dict[str, Any]], lookup_mpn: str) -> dict[str, Any]:
    """Prefer the candidate whose `ManufacturerProductNumber` matches the
    queried MPN (case-insensitive, trimmed). Fall back to first."""

    target = lookup_mpn.strip().upper()
    for p in products:
        raw = str(p.get("ManufacturerProductNumber") or "").strip().upper()
        if raw == target:
            return p
    return products[0]


def _extract_description(product: dict[str, Any]) -> tuple[str | None, str | None]:
    """Return (name, description) from DigiKey's `Description` object.

    The short `ProductDescription` is the headline; `DetailedDescription`
    is the longer one — we use them as `name` and `description` so the
    lookup endpoint can render both surfaces.
    """

    desc_node = product.get("Description") or {}
    if isinstance(desc_node, str):
        return desc_node, desc_node
    short = desc_node.get("ProductDescription")
    detailed = desc_node.get("DetailedDescription") or short
    return short, detailed


def _pick_variation(variations: list[dict[str, Any]]) -> dict[str, Any]:
    """Pick the variation that has the most complete price ladder.

    Most MPNs return a single variation (Tube/Cut Tape/Reel/etc.). When
    multiple exist, pick the first one that has a non-empty
    `StandardPricing` — that's the most useful for our lookup payload.
    """

    if not variations:
        return {}
    for v in variations:
        if v.get("StandardPricing"):
            return v
    return variations[0]


async def _build_quote(
    products: list[dict[str, Any]],
    *,
    lookup_mpn: str,
) -> SupplierQuote:
    product = _pick_product(products, lookup_mpn)
    variations = product.get("ProductVariations") or []
    variation = _pick_variation(variations)

    raw_breaks = variation.get("StandardPricing") or []
    breaks: list[SupplierPriceBreak] = []
    for entry in raw_breaks:
        qty = entry.get("BreakQuantity")
        price = entry.get("UnitPrice")
        if qty is None or price is None:
            continue
        try:
            quantity = int(qty)
            price_original = Decimal(str(price))
        except (TypeError, ValueError):
            continue
        try:
            price_eur = await fx.to_eur(price_original, _LOCALE_CURRENCY)
        except Exception:
            price_eur = None
        breaks.append(
            SupplierPriceBreak(
                quantity=quantity,
                price_original=price_original,
                currency_original=_LOCALE_CURRENCY,
                price_eur=price_eur,
            )
        )

    stock_raw = product.get("QuantityAvailable")
    try:
        stock = int(stock_raw) if stock_raw is not None else None
    except (TypeError, ValueError):
        stock = None

    resolved_mpn = (
        str(product.get("ManufacturerProductNumber") or "").strip()
        or lookup_mpn
    )
    name, description = _extract_description(product)
    manufacturer = (product.get("Manufacturer") or {}).get("Name")
    category = (product.get("Category") or {}).get("Name")
    package = (variation.get("PackageType") or {}).get("Name")
    sku = variation.get("DigiKeyProductNumber")

    return SupplierQuote(
        supplier="digikey",
        mpn=resolved_mpn,
        manufacturer=manufacturer,
        name=name,
        description=description,
        family_hint=category,
        datasheet_url=product.get("DatasheetUrl"),
        package=package,
        stock=stock,
        price_breaks=tuple(breaks),
        supplier_sku=sku,
        supplier_product_url=product.get("ProductUrl"),
        last_seen_at=datetime.now(UTC),
    )
