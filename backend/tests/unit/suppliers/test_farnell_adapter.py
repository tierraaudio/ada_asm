"""Unit tests for the Farnell adapter."""

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
from app.infrastructure.suppliers.farnell import (
    FarnellAdapter,
    _currency_for_store,
)

pytestmark = pytest.mark.asyncio

_FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "suppliers" / "farnell" / "by_mpn"

_GBP_XML = """<?xml version="1.0" encoding="UTF-8"?>
<gesmes:Envelope xmlns:gesmes="http://www.gesmes.org/xml/2002-08-01"
                 xmlns="http://www.ecb.int/vocabulary/2002-08-01/eurofxref">
  <Cube><Cube time="2026-05-29"><Cube currency="GBP" rate="0.85"/></Cube></Cube>
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
def adapter() -> FarnellAdapter:
    return FarnellAdapter(api_key="dummy-key", store_id="es.farnell.com")


async def test_hit_returns_quote_with_eur_prices(
    shared_redis: fakeredis.aioredis.FakeRedis,
    adapter: FarnellAdapter,
) -> None:
    with respx.mock() as mock:
        mock.get("https://api.element14.com/catalog/products").mock(
            return_value=httpx.Response(200, text=_load("hit.json")),
        )
        quote = await adapter.fetch_by_mpn("NE555P")

    assert quote is not None
    assert quote.supplier == "farnell"
    assert quote.mpn == "NE555P"
    assert quote.supplier_sku == "3006909"
    assert quote.manufacturer == "TEXAS INSTRUMENTS"
    # Category signal: no id, but tariff_code + displayName captured
    # (was family_hint=None before the ingest change).
    assert quote.tariff_code == "85423990"
    assert quote.supplier_category_name == quote.name
    # Datasheet now extracted from datasheets[] (was hard-coded None).
    assert quote.datasheet_url == "http://www.farnell.com/datasheets/ne555p.pdf"
    assert quote.image_url == "https://es.farnell.com/productimages/ne555p.jpg"
    codes = {c.code_type: c.code_value for c in quote.compliance}
    assert codes.get("usEccn") == "EAR99"
    assert codes.get("tariffCode") == "85423990"
    # Parametric attribute (not a compliance label) → parameters.
    plabels = {p.label for p in quote.parameters}
    assert "Voltaje de alimentación" in plabels
    assert quote.raw_payload is not None
    assert quote.stock == 14_954
    # ES store → EUR direct, identity conversion in `price_eur`.
    assert quote.supplier_product_url == "https://es.farnell.com/_/dp/3006909"
    assert len(quote.price_breaks) == 7
    first = quote.price_breaks[0]
    assert first.quantity == 1
    assert first.price_original == Decimal("0.494")
    assert first.currency_original == "EUR"
    assert first.price_eur == Decimal("0.494")


async def test_uk_store_quotes_gbp_and_converts_via_fx(
    shared_redis: fakeredis.aioredis.FakeRedis,
) -> None:
    """For uk.farnell.com the API returns GBP — adapter must run the FX
    helper to fill `price_eur` while keeping `price_original` + `currency_original`."""

    adapter = FarnellAdapter(api_key="dummy", store_id="uk.farnell.com")
    with respx.mock() as mock:
        mock.get("https://api.element14.com/catalog/products").mock(
            return_value=httpx.Response(200, text=_load("hit.json")),
        )
        mock.get(fx.ECB_DAILY_URL).mock(
            return_value=httpx.Response(200, text=_GBP_XML),
        )
        quote = await adapter.fetch_by_mpn("NE555P")

    assert quote is not None
    first = quote.price_breaks[0]
    # 0.494 GBP / 0.85 GBP-per-EUR ≈ 0.5812 EUR
    assert first.currency_original == "GBP"
    assert first.price_original == Decimal("0.494")
    assert first.price_eur is not None
    assert first.price_eur.quantize(Decimal("0.0001")) == Decimal("0.5812")


async def test_miss_returns_none(
    shared_redis: fakeredis.aioredis.FakeRedis,
    adapter: FarnellAdapter,
) -> None:
    with respx.mock() as mock:
        mock.get("https://api.element14.com/catalog/products").mock(
            return_value=httpx.Response(200, text=_load("miss.json")),
        )
        assert await adapter.fetch_by_mpn("DOES-NOT-EXIST") is None


async def test_fault_envelope_with_apikey_message_raises_auth(
    shared_redis: fakeredis.aioredis.FakeRedis,
    adapter: FarnellAdapter,
) -> None:
    with respx.mock() as mock:
        mock.get("https://api.element14.com/catalog/products").mock(
            return_value=httpx.Response(200, text=_load("auth_failed.json")),
        )
        with pytest.raises(SupplierAuthError):
            await adapter.fetch_by_mpn("anything")


async def test_http_401_raises_auth(
    shared_redis: fakeredis.aioredis.FakeRedis,
    adapter: FarnellAdapter,
) -> None:
    with respx.mock() as mock:
        mock.get("https://api.element14.com/catalog/products").mock(
            return_value=httpx.Response(401),
        )
        with pytest.raises(SupplierAuthError):
            await adapter.fetch_by_mpn("anything")


async def test_http_5xx_raises_transport(
    shared_redis: fakeredis.aioredis.FakeRedis,
    adapter: FarnellAdapter,
) -> None:
    with respx.mock() as mock:
        mock.get("https://api.element14.com/catalog/products").mock(
            return_value=httpx.Response(503),
        )
        with pytest.raises(SupplierTransportError):
            await adapter.fetch_by_mpn("anything")


async def test_non_json_raises_parse(
    shared_redis: fakeredis.aioredis.FakeRedis,
    adapter: FarnellAdapter,
) -> None:
    with respx.mock() as mock:
        mock.get("https://api.element14.com/catalog/products").mock(
            return_value=httpx.Response(200, text="<html/>"),
        )
        with pytest.raises(SupplierParseError):
            await adapter.fetch_by_mpn("anything")


async def test_picks_exact_mpn_match_over_first_candidate(
    shared_redis: fakeredis.aioredis.FakeRedis,
    adapter: FarnellAdapter,
) -> None:
    multi = {
        "keywordSearchReturn": {
            "numberOfResults": 2,
            "products": [
                {
                    "sku": "1111",
                    "displayName": "Other vendor",
                    "brandName": "OTHER",
                    "translatedManufacturerPartNumber": "OTHER-PART",
                    "prices": [{"to": 1, "from": 1, "cost": 9.99}],
                    "stock": {"level": 0},
                },
                {
                    "sku": "3006909",
                    "displayName": "Right one",
                    "brandName": "TEXAS INSTRUMENTS",
                    "translatedManufacturerPartNumber": "NE555P",
                    "prices": [{"to": 1, "from": 1, "cost": 0.494}],
                    "stock": {"level": 14954},
                },
            ],
        }
    }
    with respx.mock() as mock:
        mock.get("https://api.element14.com/catalog/products").mock(
            return_value=httpx.Response(200, json=multi),
        )
        quote = await adapter.fetch_by_mpn("ne555p")  # lower-case MPN
    assert quote is not None
    assert quote.supplier_sku == "3006909"
    assert quote.manufacturer == "TEXAS INSTRUMENTS"


def test_currency_for_store_maps_correctly() -> None:
    assert _currency_for_store("es.farnell.com") == "EUR"
    assert _currency_for_store("de.farnell.com") == "EUR"
    assert _currency_for_store("uk.farnell.com") == "GBP"
    assert _currency_for_store("ie.farnell.com") == "GBP"
    assert _currency_for_store("uk.newark.com") == "USD"
    assert _currency_for_store("") == "EUR"


def test_adapter_satisfies_protocol() -> None:
    from app.domain.repositories.supplier_adapter import SupplierAdapter

    inst = FarnellAdapter(api_key="x", store_id="es.farnell.com")
    assert isinstance(inst, SupplierAdapter)
    assert inst.code == "farnell"


def test_fixture_files_are_valid_json() -> None:
    for path in _FIXTURES.glob("*.json"):
        json.loads(path.read_text(encoding="utf-8"))
