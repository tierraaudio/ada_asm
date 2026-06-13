"""Integration test for the ingest_component CLI.

Calls the async `_ingest` coroutine directly (like the seed-script tests) so
it runs on pytest-asyncio's loop — `main()` wraps it in `asyncio.run`, which
would clash with the cached async engine's loop.
"""

from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import httpx
import pytest
import respx

from app.application.services import component_lookup_service
from app.core.exceptions import ComponentMpnNotFoundError
from app.domain.entities.supplier_quote import SupplierPriceBreak, SupplierQuote
from app.scripts.ingest_component import _build_parser, _ingest

pytestmark = pytest.mark.asyncio

_DS_URL = "http://www.farnell.com/datasheets/cli.pdf"
_PDF = b"%PDF-1.7 cli"


class _FakeAdapter:
    def __init__(self, code, quote=None):
        self.code = code
        self._quote = quote

    async def fetch_by_mpn(self, mpn):
        return self._quote


def _quote(mpn: str) -> SupplierQuote:
    return SupplierQuote(
        supplier="digikey",
        mpn=mpn,
        name="Diode CLI",
        supplier_category_id="280",
        supplier_category_name="Single Diodes",
        datasheet_url=_DS_URL,
        price_breaks=(
            SupplierPriceBreak(
                quantity=1, price_original=Decimal("0.4"), currency_original="EUR"
            ),
        ),
        stock=5,
    )


async def test_cli_ingests_and_exits_zero(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    mpn = f"CLI-{uuid4().hex[:8].upper()}"
    monkeypatch.setattr(
        component_lookup_service,
        "lookup_adapters_in_priority_order",
        lambda settings=None: [_FakeAdapter("digikey", quote=_quote(mpn))],
    )
    args = _build_parser().parse_args([mpn])
    with respx.mock() as mock:
        mock.get(_DS_URL).mock(
            return_value=httpx.Response(
                200, content=_PDF, headers={"content-type": "application/pdf"}
            )
        )
        code = await _ingest(args)

    assert code == 0
    out = capsys.readouterr().out
    assert f"Ingested {mpn}" in out
    assert "Family: Diodos" in out


async def test_cli_unknown_mpn_raises_typed_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        component_lookup_service,
        "lookup_adapters_in_priority_order",
        lambda settings=None: [_FakeAdapter("digikey", quote=None)],
    )
    args = _build_parser().parse_args(["NOPE-CLI"])
    with pytest.raises(ComponentMpnNotFoundError):
        await _ingest(args)
