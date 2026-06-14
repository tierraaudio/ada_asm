"""Unit tests for the datasheet acquisition + storage (best-effort)."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest
import respx

from app.application.services import datasheet_service
from app.domain.entities.supplier_quote import SupplierQuote
from app.infrastructure.datasheet_storage import (
    FilesystemDatasheetStorage,
    blob_path_for,
    sha256_hex,
)

pytestmark = pytest.mark.asyncio

_PDF = b"%PDF-1.7\n...fake pdf bytes..."
_HTML = b"<!DOCTYPE html><html>Access denied</html>"


def _q(supplier, datasheet_url=None, manufacturer=None) -> SupplierQuote:
    return SupplierQuote(
        supplier=supplier, mpn="LM358N", datasheet_url=datasheet_url, manufacturer=manufacturer
    )


async def test_filesystem_storage_dedups_by_content(tmp_path: Path) -> None:
    storage = FilesystemDatasheetStorage(tmp_path)
    path1 = await storage.store(_PDF)
    path2 = await storage.store(_PDF)  # identical bytes
    assert path1 == path2 == blob_path_for(sha256_hex(_PDF))
    assert await storage.exists(sha256_hex(_PDF))


async def test_acquire_archives_farnell_direct_pdf(tmp_path: Path) -> None:
    storage = FilesystemDatasheetStorage(tmp_path)
    url = "http://www.farnell.com/datasheets/lm358n.pdf"
    quotes = [_q("farnell", datasheet_url=url), _q("digikey", datasheet_url="http://x/d.pdf")]
    with respx.mock() as mock:
        mock.get(url).mock(
            return_value=httpx.Response(
                200, content=_PDF, headers={"content-type": "application/pdf"}
            )
        )
        result = await datasheet_service.acquire(quotes, mpn="LM358N", storage=storage)

    assert result.outcome == "archived"
    assert result.source == "farnell"
    assert result.blob_path == blob_path_for(sha256_hex(_PDF))
    assert result.size_bytes == len(_PDF)
    assert await storage.exists(sha256_hex(_PDF))


async def test_acquire_skips_html_interstitial_and_falls_back(tmp_path: Path) -> None:
    storage = FilesystemDatasheetStorage(tmp_path)
    # Farnell is highest priority but returns an HTML interstitial; the
    # lower-priority DigiKey URL is a real PDF and must win.
    bad = "http://www.farnell.com/datasheets/lm358n.pdf"  # returns HTML
    good = "http://ti.com/lit/ds/lm358n.pdf"
    quotes = [_q("farnell", datasheet_url=bad), _q("digikey", datasheet_url=good)]
    with respx.mock() as mock:
        mock.get(bad).mock(
            return_value=httpx.Response(
                200, content=_HTML, headers={"content-type": "text/html"}
            )
        )
        mock.get(good).mock(
            return_value=httpx.Response(
                200, content=_PDF, headers={"content-type": "application/pdf"}
            )
        )
        result = await datasheet_service.acquire(quotes, mpn="LM358N", storage=storage)

    assert result.outcome == "archived"
    assert result.source == "digikey"


async def test_acquire_retries_alternate_ua_on_403(tmp_path: Path) -> None:
    storage = FilesystemDatasheetStorage(tmp_path)
    url = "https://www.onsemi.com/download/data-sheet/pdf/lm358n-d.pdf"
    quotes = [_q("digikey", manufacturer="onsemi")]  # triggers manufacturer pattern

    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if request.headers.get("user-agent", "").startswith("Mozilla"):
            return httpx.Response(403, content=_HTML)
        return httpx.Response(
            200, content=_PDF, headers={"content-type": "application/pdf"}
        )

    with respx.mock() as mock:
        mock.get(url).mock(side_effect=handler)
        result = await datasheet_service.acquire(quotes, mpn="LM358N", storage=storage)

    assert result.outcome == "archived"
    assert result.source == "manufacturer"


async def test_acquire_link_only_when_no_pdf(tmp_path: Path) -> None:
    storage = FilesystemDatasheetStorage(tmp_path)
    url = "http://mouser.com/ds.pdf"
    quotes = [_q("mouser", datasheet_url=url)]
    with respx.mock() as mock:
        mock.get(url).mock(
            return_value=httpx.Response(
                200, content=_HTML, headers={"content-type": "text/html"}
            )
        )
        result = await datasheet_service.acquire(quotes, mpn="LM358N", storage=storage)

    assert result.outcome == "link_only"
    assert result.url == url
    assert result.blob_path is None


async def test_acquire_none_when_no_candidates(tmp_path: Path) -> None:
    storage = FilesystemDatasheetStorage(tmp_path)
    result = await datasheet_service.acquire(
        [_q("mouser")], mpn="LM358N", storage=storage
    )
    assert result.outcome == "none"


class _BrokenStorage:
    """A storage backend whose store() always raises (e.g. missing SDK/role)."""

    async def exists(self, sha256: str) -> bool:
        return False

    async def store(self, content: bytes, *, content_type: str = "application/pdf") -> str:
        raise ModuleNotFoundError("No module named 'azure.storage.blob'")

    async def read(self, blob_path: str) -> bytes:
        raise NotImplementedError


async def test_acquire_storage_failure_degrades_to_link_only() -> None:
    # A storage backend failure must NEVER fail ingestion — the datasheet
    # step is best-effort and falls back to link-only.
    url = "http://www.farnell.com/datasheets/x.pdf"
    quotes = [_q("farnell", datasheet_url=url)]
    with respx.mock() as mock:
        mock.get(url).mock(
            return_value=httpx.Response(
                200, content=_PDF, headers={"content-type": "application/pdf"}
            )
        )
        result = await datasheet_service.acquire(
            quotes, mpn="LM358N", storage=_BrokenStorage()
        )
    assert result.outcome == "link_only"
    assert result.url == url
