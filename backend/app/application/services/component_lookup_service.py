"""Service for `GET /api/v1/components/lookup?mpn=...`.

Walks the enabled suppliers in `SUPPLIER_LOOKUP_PRIORITY`, merges their
quotes progressively (first non-null wins per scalar field), caches the
final payload in Redis under `supplier_lookup:{lower(mpn)}` for
`SUPPLIER_LOOKUP_CACHE_TTL_SECONDS`, and disambiguates "no match" (404)
from "all suppliers errored" (502).
"""

from __future__ import annotations

import json
import logging
from decimal import Decimal
from typing import TYPE_CHECKING

import redis.asyncio as redis_async

from app.core.config import get_settings
from app.core.exceptions import (
    ComponentMpnNotFoundError,
    SupplierError,
    SupplierLookupUnavailableError,
)
from app.domain.entities.supplier_quote import SupplierQuote
from app.infrastructure.suppliers.registry import lookup_adapters_in_priority_order

if TYPE_CHECKING:
    from redis.asyncio.client import Redis

    from app.api.v1.schemas.lookup import (
        LookupFields,
        LookupResponse,
        SupplierData,
    )

_log = logging.getLogger(__name__)

_CACHE_KEY_PREFIX = "supplier_lookup"


def _cache_key(mpn: str) -> str:
    return f"{_CACHE_KEY_PREFIX}:{mpn.strip().lower()}"


_client: "Redis | None" = None


def _get_client() -> "Redis":
    global _client
    if _client is None:
        _client = redis_async.from_url(
            get_settings().celery_broker_url,
            decode_responses=True,
        )
    return _client


def _set_client(client: "Redis | None") -> None:
    """Test seam: inject a fakeredis client and reset between tests."""
    global _client
    _client = client


def _price_per_100(quote: SupplierQuote) -> Decimal | None:
    """Compute the cost in EUR of 100 units from a quote's price ladder.

    Picks the price break that ACTUALLY applies to a 100-unit order — the
    one with the largest `quantity` not exceeding 100. Returns None when
    every break starts above 100 or when EUR conversion failed for the
    applicable break.
    """

    if not quote.price_breaks:
        return None
    applicable = [pb for pb in quote.price_breaks if pb.quantity <= 100]
    if not applicable:
        return None
    chosen = max(applicable, key=lambda pb: pb.quantity)
    if chosen.price_eur is None:
        return None
    return chosen.price_eur * 100


def _quote_to_supplier_data(quote: SupplierQuote) -> "SupplierData":
    from app.api.v1.schemas.lookup import SupplierData, SupplierPriceBreakResponse

    return SupplierData(
        supplier=quote.supplier,
        supplier_sku=quote.supplier_sku,
        supplier_product_url=quote.supplier_product_url,
        stock=quote.stock,
        price_breaks=[
            SupplierPriceBreakResponse(
                quantity=pb.quantity,
                price_original=pb.price_original,
                currency_original=pb.currency_original,
                price_eur=pb.price_eur,
            )
            for pb in quote.price_breaks
        ],
    )


def _merge_fields(quotes: list[SupplierQuote]) -> "LookupFields":
    from app.api.v1.schemas.lookup import LookupFields
    """Progressive merge: for each scalar field, the FIRST non-null value
    encountered (priority order) wins. Later quotes only fill gaps."""

    merged: dict[str, object] = {}

    def take(key: str, value: object | None) -> None:
        # Treat empty strings as "missing" so a later supplier with real
        # data can fill the gap. Without this, Mouser's `""` for fields
        # it doesn't expose (e.g. datasheet_url) would lock the merge.
        if isinstance(value, str) and not value.strip():
            value = None
        if merged.get(key) is None and value is not None:
            merged[key] = value

    for quote in quotes:
        take("name", quote.name)
        take("description", quote.description)
        take("manufacturer", quote.manufacturer)
        take("family_hint", quote.family_hint)
        take("datasheet_url", quote.datasheet_url)
        take("package", quote.package)
        take("current_price_per_100_eur", _price_per_100(quote))

    return LookupFields(
        name=merged.get("name"),  # type: ignore[arg-type]
        description=merged.get("description"),  # type: ignore[arg-type]
        manufacturer=merged.get("manufacturer"),  # type: ignore[arg-type]
        family_hint=merged.get("family_hint"),  # type: ignore[arg-type]
        datasheet_url=merged.get("datasheet_url"),  # type: ignore[arg-type]
        package=merged.get("package"),  # type: ignore[arg-type]
        current_price_per_100_eur=merged.get("current_price_per_100_eur"),  # type: ignore[arg-type]
    )


def _missing_fields(fields: "LookupFields") -> list[str]:
    return [
        name
        for name, value in fields.model_dump().items()
        if value is None
    ]


async def lookup_by_mpn(mpn: str, *, force_refresh: bool = False) -> "LookupResponse":
    from app.api.v1.schemas.lookup import LookupResponse, SupplierData
    """Walk enabled suppliers in priority order and return a merged quote.

    Raises:
        ComponentMpnNotFoundError: at least one supplier was consulted
            successfully but none returned data for `mpn`.
        SupplierLookupUnavailableError: every consulted supplier raised
            a transport error (typed `SupplierError` subclass).
    """

    settings = get_settings()
    cache_key = _cache_key(mpn)
    redis = _get_client()

    # 1. Cache lookup (unless force_refresh).
    if not force_refresh:
        cached = await redis.get(cache_key)
        if cached:
            try:
                return LookupResponse.model_validate_json(cached)
            except (json.JSONDecodeError, ValueError):
                # Stale/corrupt cache entry — fall through to live fetch
                # and let the next write overwrite it.
                _log.info("supplier_lookup.cache.invalid mpn=%s", mpn)

    # 2. Iterate suppliers in priority order.
    adapters = lookup_adapters_in_priority_order(settings=settings)

    successful_quotes: list[SupplierQuote] = []
    supplier_data: list[SupplierData] = []
    consulted: list[str] = []
    succeeded: list[str] = []

    for adapter in adapters:
        consulted.append(adapter.code)
        try:
            quote = await adapter.fetch_by_mpn(mpn)
        except SupplierError as exc:
            _log.info(
                "supplier_lookup.adapter_error supplier=%s mpn=%s err=%s",
                adapter.code,
                mpn,
                exc,
            )
            continue

        succeeded.append(adapter.code)
        if quote is None:
            continue
        successful_quotes.append(quote)
        supplier_data.append(_quote_to_supplier_data(quote))

    # 3. Disambiguate the three outcomes.
    if not consulted:
        # No enabled+configured suppliers — treat as a 502 so the caller
        # sees a transport-level failure (the operator must enable a
        # supplier in `SUPPLIER_SYNC_ENABLED_SUPPLIERS`).
        raise SupplierLookupUnavailableError(
            "No suppliers enabled; configure SUPPLIER_SYNC_ENABLED_SUPPLIERS",
        )

    if not succeeded:
        raise SupplierLookupUnavailableError(
            f"All consulted suppliers errored: {', '.join(consulted)}",
        )

    if not successful_quotes:
        raise ComponentMpnNotFoundError(
            f"No supplier returned data for MPN {mpn!r}",
        )

    # 4. Merge + assemble response.
    fields = _merge_fields(successful_quotes)
    response = LookupResponse(
        mpn=mpn,
        found=True,
        fields=fields,
        supplier_data=supplier_data,
        sources_consulted=consulted,  # type: ignore[arg-type]
        sources_succeeded=succeeded,  # type: ignore[arg-type]
        missing_fields=_missing_fields(fields),
    )

    # 5. Cache the successful payload (TTL from settings).
    try:
        await redis.setex(
            cache_key,
            settings.supplier_lookup_cache_ttl_seconds,
            response.model_dump_json(),
        )
    except Exception as exc:  # noqa: BLE001 — cache write is best-effort
        _log.warning("supplier_lookup.cache.write_failed mpn=%s err=%s", mpn, exc)

    return response
