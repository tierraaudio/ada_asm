"""Unit tests for the Mouser Search API adapter.

Mocks the HTTP layer with respx so tests are hermetic, and the FX +
rate-limit helpers with fakeredis to keep them off the network.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from decimal import Decimal
from pathlib import Path

import fakeredis.aioredis
import httpx
import pytest
import pytest_asyncio
import respx

from app.core.exceptions import (
    SupplierAuthError,
    SupplierParseError,
    SupplierTransportError,
)
from app.infrastructure import fx, rate_limit
from app.infrastructure.suppliers.mouser import MouserAdapter

pytestmark = pytest.mark.asyncio

_FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "suppliers" / "mouser" / "by_mpn"
_ECB_XML = """<?xml version="1.0" encoding="UTF-8"?>
<gesmes:Envelope xmlns:gesmes="http://www.gesmes.org/xml/2002-08-01"
                 xmlns="http://www.ecb.int/vocabulary/2002-08-01/eurofxref">
  <Cube>
    <Cube time="2026-05-28">
      <Cube currency="USD" rate="1.10"/>
    </Cube>
  </Cube>
</gesmes:Envelope>
"""


def _load(name: str) -> str:
    return (_FIXTURES / name).read_text(encoding="utf-8")


@pytest_asyncio.fixture
async def shared_redis() -> AsyncIterator[fakeredis.aioredis.FakeRedis]:
    client = fakeredis.aioredis.FakeRedis(decode_responses=True)
    rate_limit._set_client(client)
    fx._set_client(client)
    try:
        yield client
    finally:
        await client.aclose()
        rate_limit._set_client(None)
        fx._set_client(None)


@pytest.fixture()
def adapter() -> MouserAdapter:
    return MouserAdapter(api_key="dummy-key")


async def test_hit_returns_quote_with_price_breaks(
    shared_redis: fakeredis.aioredis.FakeRedis,
    adapter: MouserAdapter,
) -> None:
    with respx.mock(assert_all_called=True) as mock:
        mock.post("https://api.mouser.com/api/v2/search/partnumber").mock(
            return_value=httpx.Response(200, text=_load("hit.json")),
        )
        mock.get(fx.ECB_DAILY_URL).mock(
            return_value=httpx.Response(200, text=_ECB_XML),
        )
        quote = await adapter.fetch_by_mpn("NBC12429FAR2G")

    assert quote is not None
    assert quote.supplier == "mouser"
    assert quote.mpn == "NBC12429FAR2G"
    assert quote.supplier_sku == "863-NBC12429FAR2G"
    assert quote.manufacturer == "onsemi"
    assert quote.datasheet_url and quote.datasheet_url.startswith("https://")
    assert quote.family_hint == "Clock & Timer ICs"
    assert quote.stock == 1240
    assert len(quote.price_breaks) == 4
    first = quote.price_breaks[0]
    assert first.quantity == 1
    assert first.price_original == Decimal("5.00")
    assert first.currency_original == "USD"
    # 5.00 USD / 1.10 USD-per-EUR ≈ 4.5454... EUR
    assert first.price_eur is not None
    assert first.price_eur.quantize(Decimal("0.0001")) == Decimal("4.5455")


async def test_miss_returns_none(
    shared_redis: fakeredis.aioredis.FakeRedis,
    adapter: MouserAdapter,
) -> None:
    with respx.mock() as mock:
        mock.post("https://api.mouser.com/api/v2/search/partnumber").mock(
            return_value=httpx.Response(200, text=_load("miss.json")),
        )
        result = await adapter.fetch_by_mpn("DOES-NOT-EXIST")
    assert result is None


async def test_invalid_api_key_payload_raises_auth(
    shared_redis: fakeredis.aioredis.FakeRedis,
    adapter: MouserAdapter,
) -> None:
    with respx.mock() as mock:
        mock.post("https://api.mouser.com/api/v2/search/partnumber").mock(
            return_value=httpx.Response(200, text=_load("auth_failed.json")),
        )
        with pytest.raises(SupplierAuthError):
            await adapter.fetch_by_mpn("anything")


async def test_http_401_raises_auth(
    shared_redis: fakeredis.aioredis.FakeRedis,
    adapter: MouserAdapter,
) -> None:
    with respx.mock() as mock:
        mock.post("https://api.mouser.com/api/v2/search/partnumber").mock(
            return_value=httpx.Response(401),
        )
        with pytest.raises(SupplierAuthError):
            await adapter.fetch_by_mpn("anything")


async def test_http_5xx_raises_transport(
    shared_redis: fakeredis.aioredis.FakeRedis,
    adapter: MouserAdapter,
) -> None:
    with respx.mock() as mock:
        mock.post("https://api.mouser.com/api/v2/search/partnumber").mock(
            return_value=httpx.Response(503),
        )
        with pytest.raises(SupplierTransportError):
            await adapter.fetch_by_mpn("anything")


async def test_non_json_raises_parse(
    shared_redis: fakeredis.aioredis.FakeRedis,
    adapter: MouserAdapter,
) -> None:
    with respx.mock() as mock:
        mock.post("https://api.mouser.com/api/v2/search/partnumber").mock(
            return_value=httpx.Response(200, text="not-json"),
        )
        with pytest.raises(SupplierParseError):
            await adapter.fetch_by_mpn("anything")


async def test_fx_failure_keeps_original_drops_eur(
    shared_redis: fakeredis.aioredis.FakeRedis,
    adapter: MouserAdapter,
) -> None:
    # ECB returns 500 → fx.to_eur raises → adapter swallows it per-break,
    # storing price_original + currency_original but leaving price_eur=None.
    with respx.mock() as mock:
        mock.post("https://api.mouser.com/api/v2/search/partnumber").mock(
            return_value=httpx.Response(200, text=_load("hit.json")),
        )
        mock.get(fx.ECB_DAILY_URL).mock(
            return_value=httpx.Response(500),
        )
        quote = await adapter.fetch_by_mpn("NBC12429FAR2G")
    assert quote is not None
    assert all(pb.price_eur is None for pb in quote.price_breaks)
    assert all(pb.currency_original == "USD" for pb in quote.price_breaks)
    assert quote.price_breaks[0].price_original == Decimal("5.00")


def test_adapter_satisfies_protocol() -> None:
    from app.domain.repositories.supplier_adapter import SupplierAdapter

    inst = MouserAdapter(api_key="x")
    assert isinstance(inst, SupplierAdapter)
    assert inst.code == "mouser"


def test_fixture_files_are_valid_json() -> None:
    for path in _FIXTURES.glob("*.json"):
        json.loads(path.read_text(encoding="utf-8"))
