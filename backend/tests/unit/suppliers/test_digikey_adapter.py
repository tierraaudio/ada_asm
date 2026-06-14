"""Unit tests for the DigiKey Product Information V4 adapter."""

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
    SupplierRateLimitedError,
    SupplierTransportError,
)
from app.infrastructure import fx, rate_limit
from app.infrastructure.suppliers import digikey as digikey_module
from app.infrastructure.suppliers.digikey import DigiKeyAdapter

pytestmark = pytest.mark.asyncio

_FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "suppliers" / "digikey" / "by_mpn"

_TOKEN_URL = "https://api.digikey.com/v1/oauth2/token"
_SEARCH_URL = "https://api.digikey.com/products/v4/search/keyword"


def _load(name: str) -> str:
    return (_FIXTURES / name).read_text(encoding="utf-8")


@pytest_asyncio.fixture
async def shared_redis() -> AsyncIterator[fakeredis.aioredis.FakeRedis]:
    client = fakeredis.aioredis.FakeRedis(decode_responses=True)
    rate_limit._set_client(client)
    fx._set_client(client)
    digikey_module._token_cache.clear()
    try:
        yield client
    finally:
        await client.aclose()
        rate_limit._set_client(None)
        fx._set_client(None)
        digikey_module._token_cache.clear()


@pytest.fixture()
def adapter() -> DigiKeyAdapter:
    return DigiKeyAdapter(
        client_id="dummy-client-id",
        client_secret="dummy-client-secret",
        token_url=_TOKEN_URL,
    )


async def test_hit_returns_quote_with_eur_breaks_and_package(
    shared_redis: fakeredis.aioredis.FakeRedis,
    adapter: DigiKeyAdapter,
) -> None:
    with respx.mock() as mock:
        mock.post(_TOKEN_URL).mock(
            return_value=httpx.Response(200, text=_load("auth_token.json")),
        )
        mock.post(_SEARCH_URL).mock(
            return_value=httpx.Response(200, text=_load("hit.json")),
        )
        quote = await adapter.fetch_by_mpn("NE555P")

    assert quote is not None
    assert quote.supplier == "digikey"
    assert quote.mpn == "NE555P"
    assert quote.supplier_sku == "296-NE555P-ND"
    assert quote.manufacturer == "Texas Instruments"
    # Category now descends to the LEAF, not the root.
    assert quote.supplier_category_id == "990"
    assert quote.supplier_category_name == ("Clock/Timing - Programmable Timers and Oscillators")
    assert quote.family_hint == quote.supplier_category_name
    assert quote.package == "Tube"
    assert quote.stock == 26_735
    assert quote.datasheet_url == "https://www.ti.com/lit/ds/symlink/na555.pdf"
    assert quote.supplier_product_url is not None
    assert "digikey.com" in quote.supplier_product_url
    assert len(quote.price_breaks) == 8
    first = quote.price_breaks[0]
    assert first.quantity == 1
    assert first.price_original == Decimal("0.43")
    assert first.currency_original == "EUR"
    assert first.price_eur == Decimal("0.43")


async def test_category_descends_to_leaf_distinguishing_diode_from_transistor(
    shared_redis: fakeredis.aioredis.FakeRedis,
    adapter: DigiKeyAdapter,
) -> None:
    # Both share root CategoryId 19; only the LEAF distinguishes them.
    with respx.mock() as mock:
        mock.post(_TOKEN_URL).mock(
            return_value=httpx.Response(200, text=_load("auth_token.json")),
        )
        mock.post(_SEARCH_URL).mock(
            return_value=httpx.Response(200, text=_load("diode_1n4148w.json")),
        )
        diode = await adapter.fetch_by_mpn("1N4148W")

    # Token is cached on the adapter after the first call — only the search
    # route is hit on the second fetch.
    with respx.mock() as mock:
        mock.post(_SEARCH_URL).mock(
            return_value=httpx.Response(200, text=_load("transistor_2n7002.json")),
        )
        transistor = await adapter.fetch_by_mpn("2N7002")

    assert diode is not None and transistor is not None
    assert diode.supplier_category_id == "280"
    assert diode.supplier_category_name == "Single Diodes"
    assert transistor.supplier_category_id == "278"
    assert transistor.supplier_category_name == "Single FETs, MOSFETs"


async def test_hit_extracts_blended_parametrics_compliance_lifecycle(
    shared_redis: fakeredis.aioredis.FakeRedis,
    adapter: DigiKeyAdapter,
) -> None:
    with respx.mock() as mock:
        mock.post(_TOKEN_URL).mock(
            return_value=httpx.Response(200, text=_load("auth_token.json")),
        )
        mock.post(_SEARCH_URL).mock(
            return_value=httpx.Response(200, text=_load("hit.json")),
        )
        quote = await adapter.fetch_by_mpn("NE555P")

    assert quote is not None
    assert quote.image_url == "https://mm.digikey.com/Volume0/opasdata/ne555p.jpg"
    assert quote.lifecycle_status == "Active"
    assert quote.lead_time_days == 42  # 6 weeks normalized to days
    assert quote.moq == 1
    # Parametrics extracted with stable ParameterId keys.
    labels = {p.label for p in quote.parameters}
    assert "Voltage - Supply" in labels
    voltage = next(p for p in quote.parameters if p.label == "Voltage - Supply")
    assert voltage.key == "2074"
    assert voltage.value == "4.5V ~ 16V"
    # Compliance codes flattened to (type, value).
    codes = {c.code_type: c.code_value for c in quote.compliance}
    assert codes.get("RohsStatus") == "ROHS3 Compliant"
    assert codes.get("ExportControlClassNumber") == "EAR99"
    assert codes.get("HtsusCode") == "8542.39.0001"
    # Raw payload preserved.
    assert quote.raw_payload is not None
    assert quote.raw_payload.get("ManufacturerProductNumber") == "NE555P"


async def test_miss_returns_none(
    shared_redis: fakeredis.aioredis.FakeRedis,
    adapter: DigiKeyAdapter,
) -> None:
    with respx.mock() as mock:
        mock.post(_TOKEN_URL).mock(
            return_value=httpx.Response(200, text=_load("auth_token.json")),
        )
        mock.post(_SEARCH_URL).mock(
            return_value=httpx.Response(200, text=_load("miss.json")),
        )
        assert await adapter.fetch_by_mpn("DOES-NOT-EXIST") is None


async def test_oauth_400_raises_auth(
    shared_redis: fakeredis.aioredis.FakeRedis,
    adapter: DigiKeyAdapter,
) -> None:
    with respx.mock() as mock:
        mock.post(_TOKEN_URL).mock(
            return_value=httpx.Response(400, json={"error": "invalid_client"}),
        )
        with pytest.raises(SupplierAuthError):
            await adapter.fetch_by_mpn("anything")


async def test_search_401_raises_auth(
    shared_redis: fakeredis.aioredis.FakeRedis,
    adapter: DigiKeyAdapter,
) -> None:
    with respx.mock() as mock:
        mock.post(_TOKEN_URL).mock(
            return_value=httpx.Response(200, text=_load("auth_token.json")),
        )
        mock.post(_SEARCH_URL).mock(return_value=httpx.Response(401))
        with pytest.raises(SupplierAuthError):
            await adapter.fetch_by_mpn("anything")


async def test_search_429_raises_rate_limited(
    shared_redis: fakeredis.aioredis.FakeRedis,
    adapter: DigiKeyAdapter,
) -> None:
    """DigiKey returns HTTP 429 when the 1000/day cap is exhausted — must
    surface as a typed rate-limit error so the sync task records the
    correct `error_code` and the lookup endpoint returns 429."""
    with respx.mock() as mock:
        mock.post(_TOKEN_URL).mock(
            return_value=httpx.Response(200, text=_load("auth_token.json")),
        )
        mock.post(_SEARCH_URL).mock(return_value=httpx.Response(429))
        with pytest.raises(SupplierRateLimitedError):
            await adapter.fetch_by_mpn("anything")


async def test_search_5xx_raises_transport(
    shared_redis: fakeredis.aioredis.FakeRedis,
    adapter: DigiKeyAdapter,
) -> None:
    with respx.mock() as mock:
        mock.post(_TOKEN_URL).mock(
            return_value=httpx.Response(200, text=_load("auth_token.json")),
        )
        mock.post(_SEARCH_URL).mock(return_value=httpx.Response(502))
        with pytest.raises(SupplierTransportError):
            await adapter.fetch_by_mpn("anything")


async def test_non_json_raises_parse(
    shared_redis: fakeredis.aioredis.FakeRedis,
    adapter: DigiKeyAdapter,
) -> None:
    with respx.mock() as mock:
        mock.post(_TOKEN_URL).mock(
            return_value=httpx.Response(200, text=_load("auth_token.json")),
        )
        mock.post(_SEARCH_URL).mock(
            return_value=httpx.Response(200, text="<not-json>"),
        )
        with pytest.raises(SupplierParseError):
            await adapter.fetch_by_mpn("anything")


async def test_token_is_cached_across_calls(
    shared_redis: fakeredis.aioredis.FakeRedis,
    adapter: DigiKeyAdapter,
) -> None:
    with respx.mock() as mock:
        auth_route = mock.post(_TOKEN_URL).mock(
            return_value=httpx.Response(200, text=_load("auth_token.json")),
        )
        mock.post(_SEARCH_URL).mock(
            return_value=httpx.Response(200, text=_load("hit.json")),
        )
        await adapter.fetch_by_mpn("NE555P")
        await adapter.fetch_by_mpn("NE555P")
        await adapter.fetch_by_mpn("NE555P")
    assert auth_route.call_count == 1


async def test_picks_exact_mpn_match_over_first_candidate(
    shared_redis: fakeredis.aioredis.FakeRedis,
    adapter: DigiKeyAdapter,
) -> None:
    multi = {
        "Products": [
            {
                "ManufacturerProductNumber": "OTHER-PART",
                "Manufacturer": {"Name": "Other"},
                "Description": {"ProductDescription": "Wrong"},
                "QuantityAvailable": 0,
                "ProductVariations": [
                    {
                        "DigiKeyProductNumber": "WRONG-ND",
                        "PackageType": {"Name": "Tape"},
                        "StandardPricing": [{"BreakQuantity": 1, "UnitPrice": 9.99}],
                    }
                ],
            },
            {
                "ManufacturerProductNumber": "NE555P",
                "Manufacturer": {"Name": "Texas Instruments"},
                "Description": {"ProductDescription": "Right one"},
                "QuantityAvailable": 26735,
                "ProductVariations": [
                    {
                        "DigiKeyProductNumber": "296-NE555P-ND",
                        "PackageType": {"Name": "Tube"},
                        "StandardPricing": [{"BreakQuantity": 1, "UnitPrice": 0.43}],
                    }
                ],
            },
        ],
        "ProductsCount": 2,
    }
    with respx.mock() as mock:
        mock.post(_TOKEN_URL).mock(
            return_value=httpx.Response(200, text=_load("auth_token.json")),
        )
        mock.post(_SEARCH_URL).mock(return_value=httpx.Response(200, json=multi))
        quote = await adapter.fetch_by_mpn("ne555p")  # lower-case MPN
    assert quote is not None
    assert quote.supplier_sku == "296-NE555P-ND"
    assert quote.manufacturer == "Texas Instruments"


async def test_variation_without_pricing_falls_back_to_first(
    shared_redis: fakeredis.aioredis.FakeRedis,
    adapter: DigiKeyAdapter,
) -> None:
    """If multiple variations exist and only some have StandardPricing, the
    adapter must prefer one with prices instead of returning a quote with
    an empty price ladder."""
    payload = {
        "Products": [
            {
                "ManufacturerProductNumber": "NE555P",
                "Manufacturer": {"Name": "TI"},
                "Description": {"ProductDescription": "Timer"},
                "QuantityAvailable": 10,
                "ProductVariations": [
                    {
                        "DigiKeyProductNumber": "EMPTY-ND",
                        "PackageType": {"Name": "Cut Tape"},
                        "StandardPricing": [],
                    },
                    {
                        "DigiKeyProductNumber": "296-NE555P-ND",
                        "PackageType": {"Name": "Tube"},
                        "StandardPricing": [{"BreakQuantity": 1, "UnitPrice": 0.43}],
                    },
                ],
            }
        ]
    }
    with respx.mock() as mock:
        mock.post(_TOKEN_URL).mock(
            return_value=httpx.Response(200, text=_load("auth_token.json")),
        )
        mock.post(_SEARCH_URL).mock(return_value=httpx.Response(200, json=payload))
        quote = await adapter.fetch_by_mpn("NE555P")
    assert quote is not None
    assert quote.supplier_sku == "296-NE555P-ND"
    assert quote.package == "Tube"
    assert len(quote.price_breaks) == 1


def test_adapter_satisfies_protocol() -> None:
    from app.domain.repositories.supplier_adapter import SupplierAdapter

    inst = DigiKeyAdapter(
        client_id="x",
        client_secret="y",
        token_url=_TOKEN_URL,
    )
    assert isinstance(inst, SupplierAdapter)
    assert inst.code == "digikey"


def test_fixture_files_are_valid_json() -> None:
    for path in _FIXTURES.glob("*.json"):
        json.loads(path.read_text(encoding="utf-8"))
