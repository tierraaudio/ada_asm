"""Integration tests for `GET /api/v1/components/lookup`.

Patches the supplier registry to return fake in-process adapters so the
endpoint exercise is fully hermetic — no respx, no real HTTP, no
fakeredis (we use the actual Redis container's `lookup` and `rate_limit`
namespaces, isolated by per-test key prefixes).
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import uuid4

import pytest
import redis.asyncio as redis_async
from httpx import AsyncClient

from app.application.services import component_lookup_service
from app.core.config import get_settings
from app.domain.entities.supplier_quote import (
    SupplierCode,
    SupplierPriceBreak,
    SupplierQuote,
)

pytestmark = pytest.mark.asyncio


class _FakeAdapter:
    """Minimal stand-in for `SupplierAdapter` used to drive the service
    without any HTTP layer. Behaviour per instance: return a quote, raise,
    or return None."""

    def __init__(
        self,
        code: SupplierCode,
        *,
        quote: SupplierQuote | None = None,
        raises: Exception | None = None,
    ) -> None:
        self.code = code
        self._quote = quote
        self._raises = raises
        self.calls = 0

    async def fetch_by_mpn(self, mpn: str) -> SupplierQuote | None:
        self.calls += 1
        if self._raises is not None:
            raise self._raises
        return self._quote


def _mouser_quote(mpn: str) -> SupplierQuote:
    return SupplierQuote(
        supplier="mouser",
        mpn=mpn,
        manufacturer="onsemi",
        name="Mouser-name",
        description="Mouser-description",
        family_hint="Clock & Timer ICs",
        datasheet_url=None,  # purposely null so DigiKey can fill it
        package=None,
        stock=1240,
        price_breaks=(
            SupplierPriceBreak(
                quantity=100,
                price_original=Decimal("0.21"),
                currency_original="EUR",
                price_eur=Decimal("0.21"),
            ),
        ),
        supplier_sku="863-MOCK",
        supplier_product_url="https://www.mouser.es/ProductDetail/onsemi/MOCK",
        last_seen_at=datetime.now(UTC),
    )


def _digikey_quote(mpn: str) -> SupplierQuote:
    return SupplierQuote(
        supplier="digikey",
        mpn=mpn,
        manufacturer="Texas Instruments",  # loses to Mouser's onsemi (Mouser is higher priority)
        name="DigiKey-name",
        description=None,
        family_hint=None,
        datasheet_url="https://www.ti.com/MOCK.pdf",  # fills Mouser's null
        package="Tube",
        stock=26735,
        price_breaks=(
            SupplierPriceBreak(
                quantity=100,
                price_original=Decimal("0.2365"),
                currency_original="EUR",
                price_eur=Decimal("0.2365"),
            ),
        ),
        supplier_sku="296-MOCK-ND",
        supplier_product_url="https://www.digikey.com/MOCK",
        last_seen_at=datetime.now(UTC),
    )


async def _flush_lookup_cache(mpn: str) -> None:
    """Remove the Redis cache entry for `mpn` so each test runs cold AND
    reset the service's module-level Redis client so a fresh connection
    is built on the test's event loop (pytest-asyncio gives each test a
    new loop; the previous loop's TCP connection is unusable)."""

    settings = get_settings()
    component_lookup_service._set_client(None)
    client = redis_async.from_url(settings.celery_broker_url, decode_responses=True)
    try:
        await client.delete(f"supplier_lookup:{mpn.lower()}")
    finally:
        await client.aclose()


def _patch_adapters(
    monkeypatch: pytest.MonkeyPatch, adapters: list[Any]
) -> None:
    """Patch the registry function the service calls so it returns our
    fake adapter list in the desired order."""

    monkeypatch.setattr(
        component_lookup_service,
        "lookup_adapters_in_priority_order",
        lambda settings=None: adapters,
    )


async def test_happy_path_merges_progressively_and_returns_supplier_data(
    api_client: AsyncClient,
    auth_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mpn = f"TEST-MERGE-{uuid4().hex[:8].upper()}"
    await _flush_lookup_cache(mpn)
    mouser = _FakeAdapter("mouser", quote=_mouser_quote(mpn))
    digikey = _FakeAdapter("digikey", quote=_digikey_quote(mpn))
    _patch_adapters(monkeypatch, [mouser, digikey])

    response = await api_client.get(
        f"/api/v1/components/lookup?mpn={mpn}",
        headers=auth_headers,
    )
    assert response.status_code == 200
    body = response.json()

    assert body["mpn"] == mpn
    assert body["found"] is True
    # Mouser is priority-first so its non-null fields win.
    assert body["fields"]["manufacturer"] == "onsemi"
    assert body["fields"]["name"] == "Mouser-name"
    # Mouser's datasheet_url is null → DigiKey fills it.
    assert body["fields"]["datasheet_url"] == "https://www.ti.com/MOCK.pdf"
    # Mouser's package is null → DigiKey fills.
    assert body["fields"]["package"] == "Tube"
    # current_price_per_100_eur from Mouser's qty=100 break → 0.21 * 100 = 21
    assert Decimal(str(body["fields"]["current_price_per_100_eur"])) == Decimal("21.00")

    assert body["sources_consulted"] == ["mouser", "digikey"]
    assert body["sources_succeeded"] == ["mouser", "digikey"]
    assert {sd["supplier"] for sd in body["supplier_data"]} == {"mouser", "digikey"}
    # Mouser sets description → field is filled, so NOT in missing_fields.
    assert body["fields"]["description"] == "Mouser-description"
    assert "description" not in body["missing_fields"]


async def test_404_when_all_suppliers_succeeded_but_no_match(
    api_client: AsyncClient,
    auth_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mpn = f"TEST-MISS-{uuid4().hex[:8].upper()}"
    await _flush_lookup_cache(mpn)
    _patch_adapters(
        monkeypatch,
        [
            _FakeAdapter("mouser", quote=None),
            _FakeAdapter("digikey", quote=None),
        ],
    )

    response = await api_client.get(
        f"/api/v1/components/lookup?mpn={mpn}",
        headers=auth_headers,
    )
    assert response.status_code == 404
    body = response.json()
    assert body["code"] == "COMPONENT_MPN_NOT_FOUND"


async def test_502_when_every_consulted_supplier_errored(
    api_client: AsyncClient,
    auth_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core.exceptions import SupplierTransportError

    mpn = f"TEST-ALL-FAIL-{uuid4().hex[:8].upper()}"
    await _flush_lookup_cache(mpn)
    _patch_adapters(
        monkeypatch,
        [
            _FakeAdapter("mouser", raises=SupplierTransportError("boom")),
            _FakeAdapter("digikey", raises=SupplierTransportError("boom")),
        ],
    )

    response = await api_client.get(
        f"/api/v1/components/lookup?mpn={mpn}",
        headers=auth_headers,
    )
    assert response.status_code == 502
    body = response.json()
    assert body["code"] == "SUPPLIER_LOOKUP_UNAVAILABLE"


async def test_partial_failure_still_returns_200_with_one_supplier(
    api_client: AsyncClient,
    auth_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core.exceptions import SupplierTransportError

    mpn = f"TEST-PARTIAL-{uuid4().hex[:8].upper()}"
    await _flush_lookup_cache(mpn)
    digikey = _FakeAdapter("digikey", quote=_digikey_quote(mpn))
    _patch_adapters(
        monkeypatch,
        [
            _FakeAdapter("mouser", raises=SupplierTransportError("boom")),
            digikey,
        ],
    )

    response = await api_client.get(
        f"/api/v1/components/lookup?mpn={mpn}",
        headers=auth_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["sources_consulted"] == ["mouser", "digikey"]
    assert body["sources_succeeded"] == ["digikey"]
    assert body["fields"]["manufacturer"] == "Texas Instruments"


async def test_422_when_mpn_too_short(
    api_client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    response = await api_client.get(
        "/api/v1/components/lookup?mpn=ab",
        headers=auth_headers,
    )
    assert response.status_code == 422


async def test_401_without_auth(api_client: AsyncClient) -> None:
    response = await api_client.get("/api/v1/components/lookup?mpn=NE555P")
    assert response.status_code == 401


async def test_cache_hit_skips_adapters_on_second_call(
    api_client: AsyncClient,
    auth_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mpn = f"TEST-CACHE-{uuid4().hex[:8].upper()}"
    await _flush_lookup_cache(mpn)
    mouser = _FakeAdapter("mouser", quote=_mouser_quote(mpn))
    _patch_adapters(monkeypatch, [mouser])

    r1 = await api_client.get(
        f"/api/v1/components/lookup?mpn={mpn}",
        headers=auth_headers,
    )
    assert r1.status_code == 200
    assert mouser.calls == 1

    r2 = await api_client.get(
        f"/api/v1/components/lookup?mpn={mpn}",
        headers=auth_headers,
    )
    assert r2.status_code == 200
    # No new adapter call — cache hit.
    assert mouser.calls == 1

    # force_refresh bypasses the cache.
    r3 = await api_client.get(
        f"/api/v1/components/lookup?mpn={mpn}&force_refresh=true",
        headers=auth_headers,
    )
    assert r3.status_code == 200
    assert mouser.calls == 2
