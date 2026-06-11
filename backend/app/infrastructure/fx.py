"""Currency conversion helper: fetch ECB daily reference rates and cache.

The European Central Bank publishes a free, no-auth XML feed updated once
per business day with EUR-quoted spot rates for every major currency:

    https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml

Schema (simplified):

    <Envelope ...>
      <Cube>
        <Cube time="2026-05-28">
          <Cube currency="USD" rate="1.0832"/>
          <Cube currency="GBP" rate="0.8519"/>
          ...
        </Cube>
      </Cube>
    </Envelope>

`rate` is **how many of the foreign currency equal 1 EUR**. To convert N
units of `currency` into EUR we divide: `eur = original / rate`.

Cached in Redis under `fx:<currency_upper>:<date_iso>` for 36 hours so a
stale weekend / holiday rate is reused without re-hitting ECB until the
next publish.
"""

from __future__ import annotations

import logging
from datetime import UTC, date
from decimal import Decimal
from typing import TYPE_CHECKING
from xml.etree import ElementTree as ET

import httpx

from app.core.exceptions import FxUnavailableError

_log = logging.getLogger(__name__)

if TYPE_CHECKING:
    from redis.asyncio.client import Redis

ECB_DAILY_URL = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml"
_NS = {"gesmes": "http://www.gesmes.org/xml/2002-08-01"}
_CACHE_TTL_SECONDS = 36 * 3600  # 36 h covers weekends + bank holidays

_HTTP_TIMEOUT_SECONDS = 8.0


def _redis_key(currency: str, on_date: date) -> str:
    return f"fx:{currency.upper()}:{on_date.isoformat()}"


def _today_utc() -> date:
    from datetime import datetime  # local to keep top-level imports tidy

    return datetime.now(UTC).date()


async def _read_cached(client: Redis[bytes], currency: str, on_date: date) -> Decimal | None:
    # Best-effort: a Redis outage degrades to a live ECB fetch instead of
    # failing the conversion (and with it the whole lookup/sync request).
    try:
        raw = await client.get(_redis_key(currency, on_date))
    except Exception as exc:
        _log.warning(
            "fx.cache.read_failed currency=%s err=%s.%s msg=%s",
            currency,
            type(exc).__module__,
            type(exc).__name__,
            exc,
        )
        return None
    if raw is None:
        return None
    try:
        return Decimal(raw.decode() if isinstance(raw, bytes) else raw)
    except (ArithmeticError, ValueError):
        return None


async def _write_cached(
    client: Redis[bytes],
    currency: str,
    on_date: date,
    rate: Decimal,
) -> None:
    try:
        await client.setex(
            _redis_key(currency, on_date),
            _CACHE_TTL_SECONDS,
            str(rate),
        )
    except Exception as exc:
        _log.warning(
            "fx.cache.write_failed currency=%s err=%s.%s msg=%s",
            currency,
            type(exc).__module__,
            type(exc).__name__,
            exc,
        )


def _parse_rates(xml_text: str) -> tuple[date, dict[str, Decimal]]:
    """Return `(rates_date, {currency: rate})` from the ECB XML payload.

    Raises `FxUnavailableError` if the document is malformed or empty —
    the caller decides whether to surface this to a `supplier_sync_errors`
    row or fail the whole request.
    """

    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        msg = f"ECB XML parse error: {exc}"
        raise FxUnavailableError(msg) from exc

    # The dated inner Cube lives at gesmes-namespaced /Envelope/Cube/Cube.
    # `findall` with a wildcard tag avoids hard-coding the namespace prefix.
    daily = None
    for cube in root.iter():
        if cube.tag.endswith("Cube") and cube.get("time"):
            daily = cube
            break

    if daily is None:
        raise FxUnavailableError("ECB XML missing dated Cube")

    rates: dict[str, Decimal] = {}
    for entry in daily.iter():
        currency = entry.get("currency")
        rate_str = entry.get("rate")
        if currency and rate_str:
            try:
                rates[currency.upper()] = Decimal(rate_str)
            except (ArithmeticError, ValueError):
                continue

    if not rates:
        raise FxUnavailableError("ECB XML contained no rates")

    rates_date = date.fromisoformat(daily.attrib["time"])
    return rates_date, rates


async def _fetch_and_cache_all(client: Redis[bytes]) -> tuple[date, dict[str, Decimal]]:
    try:
        async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT_SECONDS) as http:
            response = await http.get(ECB_DAILY_URL)
            response.raise_for_status()
    except (httpx.HTTPError, httpx.TimeoutException) as exc:
        msg = f"ECB feed unreachable: {exc}"
        raise FxUnavailableError(msg) from exc

    rates_date, rates = _parse_rates(response.text)
    for currency, rate in rates.items():
        await _write_cached(client, currency, rates_date, rate)
    return rates_date, rates


_client: Redis[bytes] | None = None


def _get_client() -> Redis[bytes]:
    global _client
    if _client is None:
        from app.infrastructure.redis_client import create_resilient_client

        _client = create_resilient_client()
    return _client


def _set_client(client: Redis[bytes] | None) -> None:
    """Test seam: swap in fakeredis for unit tests."""
    global _client
    _client = client


async def eur_rate_for(
    currency: str,
    *,
    on_date: date | None = None,
) -> Decimal:
    """Return the EUR-quoted rate (foreign units per 1 EUR) for `currency`.

    Raises `FxUnavailableError` if neither cache nor live source can
    satisfy the request. EUR itself returns `Decimal("1")` without I/O.
    """

    currency_upper = currency.upper()
    if currency_upper == "EUR":
        return Decimal("1")

    target_date = on_date or _today_utc()
    client = _get_client()

    cached = await _read_cached(client, currency_upper, target_date)
    if cached is not None:
        return cached

    rates_date, rates = await _fetch_and_cache_all(client)
    rate = rates.get(currency_upper)
    if rate is None:
        msg = f"ECB did not publish a rate for {currency_upper} on {rates_date}"
        raise FxUnavailableError(msg)
    return rate


async def to_eur(
    amount: Decimal,
    currency: str,
    *,
    on_date: date | None = None,
) -> Decimal:
    """Convert `amount` from `currency` to EUR using the daily ECB rate.

    Convenience wrapper around `eur_rate_for`.
    """

    rate = await eur_rate_for(currency, on_date=on_date)
    return amount / rate
