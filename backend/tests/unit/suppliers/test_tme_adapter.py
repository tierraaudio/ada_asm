"""Unit tests for the TME V2 adapter.

Mocks the V2 OAuth2 + REST endpoints with respx so tests are hermetic:

1. `POST /auth/token` — returns a fake JWT.
2. `GET /products/search` — returns the search payload with TME `symbol`.
3. `GET /products/data` — returns prices + stock for that symbol.

The shared FX + rate-limit Redis is faked across all tests so no network
or live container is touched.
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
from app.infrastructure.suppliers import tme as tme_module
from app.infrastructure.suppliers.tme import TmeAdapter

pytestmark = pytest.mark.asyncio

_FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "suppliers" / "tme" / "by_mpn"

_AUTH_URL = "https://api.tme.eu/auth/token"
_SEARCH_URL = "https://api.tme.eu/products/search"
_DATA_URL = "https://api.tme.eu/products/data"


def _load(name: str) -> str:
    return (_FIXTURES / name).read_text(encoding="utf-8")


@pytest_asyncio.fixture
async def shared_redis() -> AsyncIterator[fakeredis.aioredis.FakeRedis]:
    client = fakeredis.aioredis.FakeRedis(decode_responses=True)
    rate_limit._set_client(client)
    fx._set_client(client)
    # Clear the module-level token cache so the previous test's fake JWT
    # doesn't leak into the next one.
    tme_module._token_cache.clear()
    try:
        yield client
    finally:
        await client.aclose()
        rate_limit._set_client(None)
        fx._set_client(None)
        tme_module._token_cache.clear()


@pytest.fixture()
def adapter() -> TmeAdapter:
    # 50-char dummy token + 20-char dummy secret to mirror the real
    # TME naming (Basic-auth user = 50-char "private key" string).
    return TmeAdapter(
        token="x" * 50,
        app_secret="y" * 20,
    )


async def test_hit_returns_quote_with_manufacturer_symbol_as_mpn(
    shared_redis: fakeredis.aioredis.FakeRedis,
    adapter: TmeAdapter,
) -> None:
    with respx.mock() as mock:
        mock.post(_AUTH_URL).mock(
            return_value=httpx.Response(200, text=_load("auth_token.json")),
        )
        mock.get(_SEARCH_URL).mock(
            return_value=httpx.Response(200, text=_load("hit_search.json")),
        )
        mock.get(_DATA_URL).mock(
            return_value=httpx.Response(200, text=_load("hit_data.json")),
        )
        quote = await adapter.fetch_by_mpn("NE555P")

    assert quote is not None
    assert quote.supplier == "tme"
    # CRITICAL: MPN resolved from `manufacturer_symbols[]`, NOT `symbol`.
    assert quote.mpn == "NE555P"
    assert quote.supplier_sku == "NE555P"  # in this fixture symbol == MPN
    assert quote.manufacturer == "TEXAS INSTRUMENTS"
    assert quote.family_hint == "Watchdog and reset circuits"
    assert quote.description == "IC: peripheral circuit; astable,monostable,RC timer; 500kHz"
    assert quote.stock == 17_997
    assert len(quote.price_breaks) == 4
    first = quote.price_breaks[0]
    assert first.quantity == 1
    assert first.price_original == Decimal("0.39")
    assert first.currency_original == "EUR"
    # Currency=EUR was requested → identity conversion.
    assert first.price_eur == Decimal("0.39")


async def test_miss_returns_none_and_skips_data_call(
    shared_redis: fakeredis.aioredis.FakeRedis,
    adapter: TmeAdapter,
) -> None:
    """When search returns no products, the adapter MUST short-circuit and
    not waste a `/products/data` HTTP round-trip."""
    with respx.mock(assert_all_called=False) as mock:
        mock.post(_AUTH_URL).mock(
            return_value=httpx.Response(200, text=_load("auth_token.json")),
        )
        search_route = mock.get(_SEARCH_URL).mock(
            return_value=httpx.Response(200, text=_load("miss.json")),
        )
        data_route = mock.get(_DATA_URL).mock(
            return_value=httpx.Response(200, text=_load("hit_data.json")),
        )
        assert await adapter.fetch_by_mpn("DOES-NOT-EXIST") is None

    assert search_route.called
    assert not data_route.called


async def test_auth_endpoint_401_raises_auth_error(
    shared_redis: fakeredis.aioredis.FakeRedis,
    adapter: TmeAdapter,
) -> None:
    with respx.mock() as mock:
        mock.post(_AUTH_URL).mock(return_value=httpx.Response(401))
        with pytest.raises(SupplierAuthError):
            await adapter.fetch_by_mpn("anything")


async def test_search_endpoint_403_raises_auth_error(
    shared_redis: fakeredis.aioredis.FakeRedis,
    adapter: TmeAdapter,
) -> None:
    with respx.mock() as mock:
        mock.post(_AUTH_URL).mock(
            return_value=httpx.Response(200, text=_load("auth_token.json")),
        )
        mock.get(_SEARCH_URL).mock(return_value=httpx.Response(403))
        with pytest.raises(SupplierAuthError):
            await adapter.fetch_by_mpn("anything")


async def test_search_endpoint_5xx_raises_transport(
    shared_redis: fakeredis.aioredis.FakeRedis,
    adapter: TmeAdapter,
) -> None:
    with respx.mock() as mock:
        mock.post(_AUTH_URL).mock(
            return_value=httpx.Response(200, text=_load("auth_token.json")),
        )
        mock.get(_SEARCH_URL).mock(return_value=httpx.Response(503))
        with pytest.raises(SupplierTransportError):
            await adapter.fetch_by_mpn("anything")


async def test_non_json_search_raises_parse(
    shared_redis: fakeredis.aioredis.FakeRedis,
    adapter: TmeAdapter,
) -> None:
    with respx.mock() as mock:
        mock.post(_AUTH_URL).mock(
            return_value=httpx.Response(200, text=_load("auth_token.json")),
        )
        mock.get(_SEARCH_URL).mock(
            return_value=httpx.Response(200, text="<not-json>"),
        )
        with pytest.raises(SupplierParseError):
            await adapter.fetch_by_mpn("anything")


async def test_token_is_cached_across_calls(
    shared_redis: fakeredis.aioredis.FakeRedis,
    adapter: TmeAdapter,
) -> None:
    """The OAuth token endpoint MUST be hit only once across multiple
    `fetch_by_mpn` calls within the token's TTL."""
    with respx.mock() as mock:
        auth_route = mock.post(_AUTH_URL).mock(
            return_value=httpx.Response(200, text=_load("auth_token.json")),
        )
        mock.get(_SEARCH_URL).mock(
            return_value=httpx.Response(200, text=_load("hit_search.json")),
        )
        mock.get(_DATA_URL).mock(
            return_value=httpx.Response(200, text=_load("hit_data.json")),
        )
        await adapter.fetch_by_mpn("NE555P")
        await adapter.fetch_by_mpn("NE555P")
        await adapter.fetch_by_mpn("NE555P")

    assert auth_route.call_count == 1


async def test_search_matches_manufacturer_symbol_not_just_first(
    shared_redis: fakeredis.aioredis.FakeRedis,
    adapter: TmeAdapter,
) -> None:
    """When TME returns multiple candidates, the adapter must pick the one
    whose `manufacturer_symbols[]` contains the queried MPN (case-insensitive,
    trimmed) instead of blindly using the first."""

    multi_search = {
        "status": "OK",
        "data": {
            "products": {
                "elements": [
                    {
                        "symbol": "OTHER-PART",
                        "manufacturer_symbols": ["XYZ-1234"],
                        "manufacturer": {"name": "Some Vendor"},
                        "category": {"name": "Misc"},
                        "description": "Wrong match",
                    },
                    {
                        "symbol": "NE555P",
                        "manufacturer_symbols": ["NE555P"],
                        "manufacturer": {"name": "TEXAS INSTRUMENTS"},
                        "category": {"name": "Watchdog and reset circuits"},
                        "description": "Right one",
                    },
                ]
            }
        },
    }

    with respx.mock() as mock:
        mock.post(_AUTH_URL).mock(
            return_value=httpx.Response(200, text=_load("auth_token.json")),
        )
        mock.get(_SEARCH_URL).mock(
            return_value=httpx.Response(200, json=multi_search),
        )
        mock.get(_DATA_URL).mock(
            return_value=httpx.Response(200, text=_load("hit_data.json")),
        )
        quote = await adapter.fetch_by_mpn("ne555p")  # lower-case MPN

    assert quote is not None
    assert quote.supplier_sku == "NE555P"
    assert quote.manufacturer == "TEXAS INSTRUMENTS"


def test_adapter_satisfies_protocol() -> None:
    from app.domain.repositories.supplier_adapter import SupplierAdapter

    inst = TmeAdapter(token="x" * 50, app_secret="y" * 20)
    assert isinstance(inst, SupplierAdapter)
    assert inst.code == "tme"


def test_fixture_files_are_valid_json() -> None:
    for path in _FIXTURES.glob("*.json"):
        json.loads(path.read_text(encoding="utf-8"))
