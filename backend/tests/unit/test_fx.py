"""Unit tests for the ECB FX helper.

Hits a respx-mocked ECB endpoint so tests are hermetic and deterministic.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import date
from decimal import Decimal

import fakeredis.aioredis
import httpx
import pytest
import pytest_asyncio
import respx

from app.core.exceptions import FxUnavailableError
from app.infrastructure import fx


pytestmark = pytest.mark.asyncio


_SAMPLE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<gesmes:Envelope xmlns:gesmes="http://www.gesmes.org/xml/2002-08-01"
                 xmlns="http://www.ecb.int/vocabulary/2002-08-01/eurofxref">
  <gesmes:subject>Reference rates</gesmes:subject>
  <gesmes:Sender><gesmes:name>European Central Bank</gesmes:name></gesmes:Sender>
  <Cube>
    <Cube time="2026-05-28">
      <Cube currency="USD" rate="1.0832"/>
      <Cube currency="GBP" rate="0.8519"/>
      <Cube currency="JPY" rate="169.45"/>
    </Cube>
  </Cube>
</gesmes:Envelope>
"""


@pytest_asyncio.fixture
async def fake_redis() -> AsyncIterator[fakeredis.aioredis.FakeRedis]:
    client = fakeredis.aioredis.FakeRedis(decode_responses=True)
    fx._set_client(client)
    try:
        yield client
    finally:
        await client.aclose()
        fx._set_client(None)


async def test_eur_returns_one_without_io(
    fake_redis: fakeredis.aioredis.FakeRedis,
) -> None:
    # No respx mock — proves we don't even call the HTTP layer for EUR.
    assert await fx.eur_rate_for("EUR") == Decimal("1")
    assert await fx.eur_rate_for("eur") == Decimal("1")


async def test_fetches_and_caches_on_first_call(
    fake_redis: fakeredis.aioredis.FakeRedis,
) -> None:
    target = date(2026, 5, 28)
    with respx.mock(assert_all_called=True) as mock:
        mock.get(fx.ECB_DAILY_URL).mock(
            return_value=httpx.Response(200, text=_SAMPLE_XML),
        )
        usd_rate = await fx.eur_rate_for("USD", on_date=target)
    assert usd_rate == Decimal("1.0832")
    # Subsequent calls within TTL must hit the cache, NOT the network.
    with respx.mock(assert_all_called=False) as mock_no_call:
        mock_no_call.get(fx.ECB_DAILY_URL).mock(
            return_value=httpx.Response(500),
        )
        again = await fx.eur_rate_for("USD", on_date=target)
    assert again == Decimal("1.0832")


async def test_unknown_currency_raises(
    fake_redis: fakeredis.aioredis.FakeRedis,
) -> None:
    target = date(2026, 5, 28)
    with respx.mock() as mock:
        mock.get(fx.ECB_DAILY_URL).mock(
            return_value=httpx.Response(200, text=_SAMPLE_XML),
        )
        with pytest.raises(FxUnavailableError):
            await fx.eur_rate_for("XYZ", on_date=target)


async def test_http_error_raises_fx_unavailable(
    fake_redis: fakeredis.aioredis.FakeRedis,
) -> None:
    with respx.mock() as mock:
        mock.get(fx.ECB_DAILY_URL).mock(
            return_value=httpx.Response(503),
        )
        with pytest.raises(FxUnavailableError):
            await fx.eur_rate_for("USD", on_date=date(2026, 5, 28))


async def test_malformed_xml_raises(
    fake_redis: fakeredis.aioredis.FakeRedis,
) -> None:
    with respx.mock() as mock:
        mock.get(fx.ECB_DAILY_URL).mock(
            return_value=httpx.Response(200, text="<not-valid-xml>"),
        )
        with pytest.raises(FxUnavailableError):
            await fx.eur_rate_for("USD", on_date=date(2026, 5, 28))


async def test_to_eur_converts_correctly(
    fake_redis: fakeredis.aioredis.FakeRedis,
) -> None:
    target = date(2026, 5, 28)
    with respx.mock() as mock:
        mock.get(fx.ECB_DAILY_URL).mock(
            return_value=httpx.Response(200, text=_SAMPLE_XML),
        )
        # USD 10.83 / 1.0832 ≈ 9.998... EUR
        eur = await fx.to_eur(Decimal("10.83"), "USD", on_date=target)
    assert eur.quantize(Decimal("0.0001")) == Decimal("9.9982")
