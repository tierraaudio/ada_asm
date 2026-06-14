"""Integration tests for POST /components/ingest + GET /{id}/datasheet."""

from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import httpx
import pytest
import respx
from httpx import AsyncClient

from app.application.services import component_lookup_service
from app.domain.entities.supplier_quote import (
    SupplierComplianceCode,
    SupplierParameter,
    SupplierPriceBreak,
    SupplierQuote,
)

pytestmark = pytest.mark.asyncio

_DS_URL = "http://www.farnell.com/datasheets/ne.pdf"
_PDF = b"%PDF-1.7 ingest-api fake"


class _FakeAdapter:
    def __init__(self, code, quote=None, raises=None):
        self.code = code
        self._quote = quote
        self._raises = raises

    async def fetch_by_mpn(self, mpn):
        if self._raises is not None:
            raise self._raises
        return self._quote


def _quote(mpn: str) -> SupplierQuote:
    return SupplierQuote(
        supplier="digikey",
        mpn=mpn,
        manufacturer="Texas Instruments",
        name="Diode X",
        supplier_category_id="280",
        supplier_category_name="Single Diodes",
        datasheet_url=_DS_URL,
        lifecycle_status="Active",
        moq=1,
        parameters=(SupplierParameter(label="Voltage", value="16V"),),
        compliance=(SupplierComplianceCode(code_type="ECCN", code_value="EAR99"),),
        price_breaks=(
            SupplierPriceBreak(quantity=1, price_original=Decimal("0.4"), currency_original="EUR"),
        ),
        country_of_origin="MX",
        raw_payload={"x": 1},
        stock=10,
    )


def _patch(monkeypatch, adapters):
    monkeypatch.setattr(
        component_lookup_service,
        "lookup_adapters_in_priority_order",
        lambda settings=None: adapters,
    )


async def test_ingest_endpoint_returns_component_and_report(
    api_client: AsyncClient,
    auth_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mpn = f"APIING-{uuid4().hex[:8].upper()}"
    _patch(monkeypatch, [_FakeAdapter("digikey", quote=_quote(mpn))])
    with respx.mock() as mock:
        mock.get(_DS_URL).mock(
            return_value=httpx.Response(
                200, content=_PDF, headers={"content-type": "application/pdf"}
            )
        )
        resp = await api_client.post(
            "/api/v1/components/ingest",
            json={"mpn": mpn, "ubicacion": "G-T-9"},
            headers=auth_headers,
        )

    assert resp.status_code == 201
    body = resp.json()
    assert body["component"]["family"] == "Diodos"
    assert body["component"]["sku"].startswith("DIO-")
    assert body["component"]["location"] == "G-T-9"
    report = body["report"]
    assert report["status"] == "ok"
    assert report["family"]["inferred"] == "Diodos"
    assert report["datasheet"]["outcome"] == "archived"
    assert report["counts"]["parameters"] == 1
    assert "location" in report["manual_overrides_applied"]

    # Datasheet endpoint streams the archived PDF.
    component_id = body["component"]["id"]
    ds_resp = await api_client.get(
        f"/api/v1/components/{component_id}/datasheet", headers=auth_headers
    )
    assert ds_resp.status_code == 200
    assert ds_resp.headers["content-type"].startswith("application/pdf")
    assert ds_resp.content == _PDF


async def test_ingest_unknown_mpn_returns_404(
    api_client: AsyncClient,
    auth_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch(monkeypatch, [_FakeAdapter("digikey", quote=None)])
    resp = await api_client.post(
        "/api/v1/components/ingest", json={"mpn": "NOPE"}, headers=auth_headers
    )
    assert resp.status_code == 404
    assert resp.json()["code"] == "COMPONENT_MPN_NOT_FOUND"


async def test_ingest_requires_auth(api_client: AsyncClient) -> None:
    resp = await api_client.post("/api/v1/components/ingest", json={"mpn": "X"})
    assert resp.status_code == 401


async def test_datasheet_404_when_none_archived(
    api_client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    resp = await api_client.get(f"/api/v1/components/{uuid4()}/datasheet", headers=auth_headers)
    assert resp.status_code == 404
