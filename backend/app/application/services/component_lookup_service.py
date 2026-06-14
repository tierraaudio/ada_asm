"""Service for `GET /api/v1/components/lookup?mpn=...`.

Walks the enabled suppliers in `SUPPLIER_LOOKUP_PRIORITY`, merges their
quotes progressively (first non-null wins per scalar field), caches the
final payload in Redis under `supplier_lookup:{lower(mpn)}` for
`SUPPLIER_LOOKUP_CACHE_TTL_SECONDS`, and disambiguates "no match" (404)
from "all suppliers errored" (502).
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from decimal import Decimal
from typing import TYPE_CHECKING

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

# Hard ceiling on each cache round-trip. The cache is an optimisation:
# if Redis can't answer in this window the lookup proceeds straight to
# the suppliers rather than stalling the request.
_CACHE_OP_TIMEOUT_SECONDS = 5.0


def _cache_key(mpn: str) -> str:
    return f"{_CACHE_KEY_PREFIX}:{mpn.strip().lower()}"


_client: Redis[bytes] | None = None


def _get_client() -> Redis[bytes]:
    global _client
    if _client is None:
        from app.infrastructure.redis_client import create_resilient_client

        _client = create_resilient_client()
    return _client


def _set_client(client: Redis[bytes] | None) -> None:
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


def _quote_to_supplier_data(quote: SupplierQuote) -> SupplierData:
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
        supplier_category_id=quote.supplier_category_id,
        supplier_category_name=quote.supplier_category_name,
        tariff_code=quote.tariff_code,
    )


def _merge_fields(quotes: list[SupplierQuote]) -> LookupFields:
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
        take("datasheet_url", quote.datasheet_url)
        take("package", quote.package)
        take("current_price_per_100_eur", _price_per_100(quote))

    # `family_hint` is intentionally NOT merged here: the presentation
    # priority order (Mouser first) inverts the category signal-strength
    # order (DigiKey/TME stable ids first). The family is resolved by
    # FamilyInferenceService from the per-supplier signals carried in
    # `supplier_data[]`. See change `ingest-component-from-mpn`.
    return LookupFields(
        name=merged.get("name"),
        description=merged.get("description"),
        manufacturer=merged.get("manufacturer"),
        family_hint=None,
        datasheet_url=merged.get("datasheet_url"),
        package=merged.get("package"),
        current_price_per_100_eur=merged.get("current_price_per_100_eur"),
    )


def _missing_fields(fields: LookupFields) -> list[str]:
    return [name for name, value in fields.model_dump().items() if value is None]


async def gather_quotes(mpn: str) -> tuple[list[SupplierQuote], list[str], list[str]]:
    """Walk enabled suppliers LIVE (no cache) for ingestion.

    Returns `(quotes, consulted, succeeded)`. Raises the same three-outcome
    disambiguation as `lookup_by_mpn`: `SupplierLookupUnavailableError` when
    no supplier is enabled or all errored, `ComponentMpnNotFoundError` when
    suppliers responded but none recognised the MPN.
    """

    settings = get_settings()
    adapters = lookup_adapters_in_priority_order(settings=settings)
    quotes: list[SupplierQuote] = []
    consulted: list[str] = []
    succeeded: list[str] = []

    for adapter in adapters:
        consulted.append(adapter.code)
        try:
            quote = await adapter.fetch_by_mpn(mpn)
        except SupplierError as exc:
            _log.info(
                "ingest.adapter_error supplier=%s mpn=%s err=%s",
                adapter.code,
                mpn,
                exc,
            )
            continue
        succeeded.append(adapter.code)
        if quote is not None:
            quotes.append(quote)

    if not consulted:
        raise SupplierLookupUnavailableError(
            "No suppliers enabled; configure SUPPLIER_SYNC_ENABLED_SUPPLIERS",
        )
    if not succeeded:
        raise SupplierLookupUnavailableError(
            f"All consulted suppliers errored: {', '.join(consulted)}",
        )
    if not quotes:
        raise ComponentMpnNotFoundError(
            f"No supplier returned data for MPN {mpn!r}",
        )
    return quotes, consulted, succeeded


async def lookup_by_mpn(mpn: str, *, force_refresh: bool = False) -> LookupResponse:
    from app.api.v1.schemas.lookup import LookupResponse

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
    started = time.monotonic()
    cache_state = "bypass" if force_refresh else "miss"

    # 1. Cache lookup (unless force_refresh). Best-effort: a Redis outage
    # must degrade to a live fetch, never fail or stall the request.
    if not force_refresh:
        try:
            cached = await asyncio.wait_for(redis.get(cache_key), timeout=_CACHE_OP_TIMEOUT_SECONDS)
        except Exception as exc:
            cache_state = "error"
            _log.warning(
                "supplier_lookup.cache.read_failed mpn=%s err=%s.%s msg=%s",
                mpn,
                type(exc).__module__,
                type(exc).__name__,
                exc,
            )
            cached = None
        if cached:
            try:
                response = LookupResponse.model_validate_json(cached)
            except (json.JSONDecodeError, ValueError):
                # Stale/corrupt cache entry — fall through to live fetch
                # and let the next write overwrite it.
                _log.info("supplier_lookup.cache.invalid mpn=%s", mpn)
            else:
                _log.info(
                    "supplier_lookup.done mpn=%s cache=hit duration_ms=%d",
                    mpn,
                    (time.monotonic() - started) * 1000,
                )
                return response

    # 2. Iterate suppliers in priority order.
    adapters = lookup_adapters_in_priority_order(settings=settings)

    successful_quotes: list[SupplierQuote] = []
    supplier_data: list[SupplierData] = []
    consulted: list[str] = []
    succeeded: list[str] = []
    adapter_timings: list[str] = []

    for adapter in adapters:
        consulted.append(adapter.code)
        adapter_started = time.monotonic()
        try:
            quote = await adapter.fetch_by_mpn(mpn)
        except SupplierError as exc:
            adapter_timings.append(
                f"{adapter.code}:{(time.monotonic() - adapter_started) * 1000:.0f}ms:error"
            )
            _log.info(
                "supplier_lookup.adapter_error supplier=%s mpn=%s err=%s",
                adapter.code,
                mpn,
                exc,
            )
            continue

        succeeded.append(adapter.code)
        adapter_timings.append(
            f"{adapter.code}:{(time.monotonic() - adapter_started) * 1000:.0f}ms:"
            f"{'match' if quote is not None else 'no_match'}"
        )
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
        sources_consulted=consulted,
        sources_succeeded=succeeded,
        missing_fields=_missing_fields(fields),
    )

    # 5. Cache the successful payload (TTL from settings). Best-effort.
    try:
        await asyncio.wait_for(
            redis.setex(
                cache_key,
                settings.supplier_lookup_cache_ttl_seconds,
                response.model_dump_json(),
            ),
            timeout=_CACHE_OP_TIMEOUT_SECONDS,
        )
    except Exception as exc:
        _log.warning(
            "supplier_lookup.cache.write_failed mpn=%s err=%s.%s msg=%s",
            mpn,
            type(exc).__module__,
            type(exc).__name__,
            exc,
        )

    _log.info(
        "supplier_lookup.done mpn=%s cache=%s duration_ms=%d adapters=[%s]",
        mpn,
        cache_state,
        (time.monotonic() - started) * 1000,
        ",".join(adapter_timings),
    )
    return response
