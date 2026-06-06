"""TME API v2 adapter (REST + OAuth2).

The legacy v1 (Products/Search.json + HMAC-SHA1) is gone — TME's modern
v2 API uses OAuth2 client-credentials over HTTP Basic. The flow:

1. `POST https://api.tme.eu/auth/token` with HTTP Basic auth:
   - username = the **50-character token** (env: `TME_TOKEN`)
   - password = the **20-character application secret** (env: `TME_APP_SECRET`)
   Returns a short-lived (~300s) JWT bearer token. We cache it in Redis
   under `tme:access_token` with TTL = `expires_in - 30s` headroom.

2. `GET /products/search?phrase=<MPN>&scope[]=products&country=ES&language=EN`
   with `Authorization: Bearer <jwt>` — returns one or more TME products.
   The manufacturer's MPN lives in `manufacturer_symbols[]`; the supplier's
   own SKU is `symbol`.

3. `GET /products/data?symbols[]=<symbol>&scope[]=prices&scope[]=stock&country=ES&currency=EUR`
   — returns the matched product's price ladder + current stock snapshot.

Two HTTP round-trips per `fetch_by_mpn` call (≈ 600ms total). Both are
rate-limited under one shared bucket (`supplier:tme`, 20 req/min).
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
from app.infrastructure import rate_limit

_BASE_URL = "https://api.tme.eu"
_TOKEN_URL = f"{_BASE_URL}/auth/token"
_SEARCH_URL = f"{_BASE_URL}/products/search"
_DATA_URL = f"{_BASE_URL}/products/data"

_HTTP_TIMEOUT_SECONDS = 10.0
_RATE_LIMIT_PER_MINUTE = 20
_BUCKET = "supplier:tme"

_DEFAULT_COUNTRY = "ES"
_DEFAULT_CURRENCY = "EUR"
_DEFAULT_LANGUAGE = "EN"

# In-process token cache — keyed by (token, app_secret) so two adapters
# with different credentials don't trample each other.
_token_cache: dict[tuple[str, str], tuple[str, float]] = {}


class TmeAdapter:
    """`SupplierAdapter` for the TME v2 REST API."""

    code: SupplierCode = "tme"

    def __init__(self, *, token: str, app_secret: str) -> None:
        # `token` and `app_secret` follow TME's V2 naming:
        # `token` is the 50-char string (Basic-auth username),
        # `app_secret` is the 20-char string (Basic-auth password).
        self._token = token
        self._app_secret = app_secret

    async def _get_access_token(self) -> str:
        cache_key = (self._token, self._app_secret)
        cached = _token_cache.get(cache_key)
        if cached is not None:
            value, expires_at = cached
            if time.time() < expires_at:
                return value

        try:
            async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT_SECONDS) as client:
                response = await client.post(
                    _TOKEN_URL,
                    auth=(self._token, self._app_secret),
                    data={"grant_type": "client_credentials"},
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )
        except httpx.TimeoutException as exc:
            raise SupplierTimeoutError(f"TME auth timed out: {exc}") from exc
        except httpx.HTTPError as exc:
            raise SupplierTransportError(f"TME auth HTTP error: {exc}") from exc

        if response.status_code in (401, 403):
            raise SupplierAuthError(
                f"TME auth rejected credentials (HTTP {response.status_code})",
            )
        if response.status_code != 200:
            raise SupplierTransportError(
                f"TME auth HTTP {response.status_code}",
            )

        try:
            payload = response.json()
            access_token = payload["access_token"]
            expires_in = int(payload.get("expires_in", 300))
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            raise SupplierParseError(f"TME auth response shape: {exc}") from exc

        # Refresh 30 s early to avoid using a token that expires mid-call.
        _token_cache[cache_key] = (access_token, time.time() + expires_in - 30)
        return access_token

    async def fetch_by_mpn(self, mpn: str) -> SupplierQuote | None:
        # Two API calls share one rate-limit budget so we apply it twice.
        await rate_limit.acquire(_BUCKET, _RATE_LIMIT_PER_MINUTE)
        access_token = await self._get_access_token()
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept-Language": _DEFAULT_LANGUAGE.lower(),
        }

        # ---- Step 1: search ----
        search_params: list[tuple[str, str]] = [
            ("country", _DEFAULT_COUNTRY),
            ("language", _DEFAULT_LANGUAGE),
            ("phrase", mpn),
            ("scope[]", "products"),
            ("limit", "5"),
        ]
        search_body = await _get_json(_SEARCH_URL, search_params, headers)
        # `data.products.elements[]` per V2 spec. Older accounts have
        # returned a list at `data.products` directly; accept both shapes.
        products_node = (search_body.get("data") or {}).get("products") or {}
        if isinstance(products_node, dict):
            candidates = products_node.get("elements") or []
        else:
            candidates = products_node
        if not candidates:
            return None

        # Pick the candidate whose manufacturer_symbols contains the MPN we
        # asked for. Fallback: first candidate.
        mpn_upper = mpn.strip().upper()
        product = next(
            (
                p
                for p in candidates
                if any(
                    str(sym).strip().upper() == mpn_upper
                    for sym in (p.get("manufacturer_symbols") or [])
                )
            ),
            candidates[0],
        )

        symbol = product.get("symbol")
        if not symbol:
            raise SupplierParseError("TME search product missing `symbol`")

        # ---- Step 2: data (prices + stock) ----
        await rate_limit.acquire(_BUCKET, _RATE_LIMIT_PER_MINUTE)
        data_params: list[tuple[str, str]] = [
            ("country", _DEFAULT_COUNTRY),
            ("currency", _DEFAULT_CURRENCY),
            ("language", _DEFAULT_LANGUAGE),
            ("symbols[]", str(symbol)),
            ("scope[]", "prices"),
            ("scope[]", "stock"),
        ]
        data_body = await _get_json(_DATA_URL, data_params, headers)
        # `/products/data` returns the list directly under `data.elements[]`
        # (NOT `data.products.elements[]` — different shape than /search).
        data_elements = (data_body.get("data") or {}).get("elements") or []
        data_row = data_elements[0] if data_elements else {}

        try:
            return await _build_quote(product, data_row, lookup_mpn=mpn)
        except (KeyError, TypeError, InvalidOperation) as exc:
            raise SupplierParseError(f"TME response shape: {exc}") from exc


async def _get_json(
    url: str, params: list[tuple[str, str]], headers: dict[str, str]
) -> dict[str, Any]:
    """Shared GET wrapper that maps HTTP/transport errors to typed exceptions."""

    try:
        async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT_SECONDS) as client:
            response = await client.get(url, params=params, headers=headers)
    except httpx.TimeoutException as exc:
        raise SupplierTimeoutError(f"TME timed out: {exc}") from exc
    except httpx.HTTPError as exc:
        raise SupplierTransportError(f"TME HTTP error: {exc}") from exc

    if response.status_code >= 500:
        raise SupplierTransportError(f"TME HTTP {response.status_code}")
    if response.status_code in (401, 403):
        raise SupplierAuthError(f"TME HTTP {response.status_code} on auth")
    if response.status_code == 404:
        # V2 reports unknown action as 404; treat as transport failure so the
        # caller doesn't confuse it with the in-payload "no match" signal.
        raise SupplierTransportError(f"TME HTTP 404 {url}")
    if response.status_code != 200:
        raise SupplierTransportError(f"TME HTTP {response.status_code}")

    try:
        return response.json()
    except json.JSONDecodeError as exc:
        raise SupplierParseError(f"TME non-JSON response: {exc}") from exc


def _extract_price_breaks(data_row: dict[str, Any]) -> list[SupplierPriceBreak]:
    """Map TME v2's price ladder into our domain shape.

    Shape in the wild: `prices.amounts[]` where each element is
    `{amount: int, price: number, special: bool}`. We asked TME for EUR
    so `price_eur == price_original` (identity conversion).
    """

    # `prices.elements[]` — list of `{amount, price, special}`. The wrapper
    # also exposes `tax`, `currency`, `type` (NET / GROSS) which we ignore
    # because we asked TME for NET EUR explicitly.
    prices_node = data_row.get("prices") or {}
    raw_breaks = prices_node.get("elements") or []
    breaks: list[SupplierPriceBreak] = []
    for entry in raw_breaks:
        amount = entry.get("amount")
        price_value = entry.get("price")
        if amount is None or price_value is None:
            continue
        try:
            qty = int(amount)
            price_original = Decimal(str(price_value))
        except (TypeError, ValueError):
            continue
        breaks.append(
            SupplierPriceBreak(
                quantity=qty,
                price_original=price_original,
                currency_original=_DEFAULT_CURRENCY,
                price_eur=price_original,
            )
        )
    return breaks


async def _build_quote(
    product: dict[str, Any],
    data_row: dict[str, Any],
    *,
    lookup_mpn: str,
) -> SupplierQuote:
    breaks = _extract_price_breaks(data_row)

    # `/products/data` exposes the current snapshot under `stock_quantity`.
    stock_raw: Any = data_row.get("stock_quantity")
    try:
        stock = int(stock_raw) if stock_raw is not None else None
    except (TypeError, ValueError):
        stock = None

    manufacturer_symbols = product.get("manufacturer_symbols") or []
    resolved_mpn = (
        next(
            (
                str(sym).strip()
                for sym in manufacturer_symbols
                if str(sym).strip().upper() == lookup_mpn.strip().upper()
            ),
            None,
        )
        or (str(manufacturer_symbols[0]).strip() if manufacturer_symbols else lookup_mpn)
    )

    manufacturer = (product.get("manufacturer") or {}).get("name")
    category = (product.get("category") or {}).get("name")
    product_url = product.get("product_information_page") or product.get("url")
    datasheet = product.get("document_url") or product.get("datasheet_url")

    return SupplierQuote(
        supplier="tme",
        mpn=resolved_mpn,
        manufacturer=manufacturer,
        name=product.get("description"),
        description=product.get("description"),
        family_hint=category,
        datasheet_url=datasheet,
        package=None,
        stock=stock,
        price_breaks=tuple(breaks),
        supplier_sku=product.get("symbol"),
        supplier_product_url=product_url,
        last_seen_at=datetime.now(UTC),
    )
