"""Acquire + archive a component's datasheet PDF (best-effort).

Tries candidate URLs in a fallback chain (Farnell direct → DigiKey →
manufacturer URL pattern → other suppliers), validating each download is a
real PDF before archiving it to `DatasheetStorage`. NEVER blocks component
creation: when nothing yields a PDF, returns a link-only result. See change
`ingest-component-from-mpn` (datasheet-archival) and the research report for
the live-probed per-host gotchas.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

import httpx

from app.domain.entities.supplier_quote import SupplierQuote
from app.infrastructure.datasheet_storage import DatasheetStorage, sha256_hex

_log = logging.getLogger(__name__)

_PDF_MAGIC = b"%PDF"
_HTTP_TIMEOUT_SECONDS = 20.0
# Global budget for the whole acquisition chain so a sequence of slow/hanging
# candidate hosts can never make ingestion hang (observed: some MPNs walked
# several slow URLs for >100s). On expiry we fall back to link-only.
_ACQUIRE_BUDGET_SECONDS = 40.0
_MAX_PDF_BYTES = 64 * 1024 * 1024  # 64 MB safety cap

# Per-host User-Agent strategy (live-probed). Some manufacturer hosts only
# serve PDFs to a curl-like UA, others require a browser UA.
_BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
_CURL_UA = "curl/8.4.0"
# Supplier priority for picking a datasheet URL: Farnell gives reliably
# direct PDFs; DigiKey often a direct manufacturer PDF; then the rest.
_SUPPLIER_URL_PRIORITY = ("farnell", "digikey", "mouser", "tme", "rs")


@dataclass(frozen=True)
class DatasheetResult:
    outcome: str  # "archived" | "link_only" | "none"
    source: str | None = None
    url: str | None = None
    blob_path: str | None = None
    sha256: str | None = None
    content_type: str | None = None
    size_bytes: int | None = None


def _manufacturer_pattern_url(manufacturer: str | None, mpn: str) -> str | None:
    """Deterministic manufacturer datasheet URL when the brand is known."""

    if not manufacturer:
        return None
    m = manufacturer.lower()
    part = mpn.strip().lower()
    if "texas" in m or m == "ti":
        return f"https://www.ti.com/lit/ds/symlink/{part}.pdf"
    if "espressif" in m:
        return f"https://www.espressif.com/sites/default/files/documentation/{part}_datasheet_en.pdf"
    if "onsemi" in m or "on semi" in m:
        return f"https://www.onsemi.com/download/data-sheet/pdf/{part}-d.pdf"
    return None


def _candidate_urls(quotes: list[SupplierQuote], mpn: str) -> list[tuple[str, str]]:
    """Ordered (source, url) candidates, de-duplicated, stop-at-first-success."""

    by_supplier: dict[str, SupplierQuote] = {q.supplier: q for q in quotes}
    candidates: list[tuple[str, str]] = []
    seen: set[str] = set()

    def add(source: str, url: str | None) -> None:
        if url and url not in seen:
            seen.add(url)
            candidates.append((source, url))

    for supplier in _SUPPLIER_URL_PRIORITY:
        quote = by_supplier.get(supplier)
        if quote:
            add(supplier, quote.datasheet_url)
    # Manufacturer pattern, derived from the first known manufacturer.
    manufacturer = next((q.manufacturer for q in quotes if q.manufacturer), None)
    add("manufacturer", _manufacturer_pattern_url(manufacturer, mpn))
    return candidates


def _normalize_url(url: str) -> str:
    """Protocol-relative URLs (TME) → https."""

    if url.startswith("//"):
        return f"https:{url}"
    return url


async def _try_download(url: str) -> tuple[bytes, str] | None:
    """Download `url`, return (content, content_type) iff it is a real PDF.

    Follows redirects; validates final Content-Type == application/pdf AND
    the body starts with the %PDF magic bytes. Retries with an alternate
    User-Agent on a 403 before giving up.
    """

    target = _normalize_url(url)
    for ua in (_CURL_UA, _BROWSER_UA):
        try:
            async with httpx.AsyncClient(
                follow_redirects=True, timeout=_HTTP_TIMEOUT_SECONDS
            ) as client:
                resp = await client.get(target, headers={"User-Agent": ua})
        except httpx.HTTPError as exc:
            _log.info("datasheet.fetch_error url=%s err=%s", target, exc)
            return None
        if resp.status_code == 403:
            continue  # try the alternate UA
        if resp.status_code != 200:
            return None
        content_type = (resp.headers.get("content-type") or "").split(";")[0].strip()
        content = resp.content
        if content_type != "application/pdf" or not content.startswith(_PDF_MAGIC):
            _log.info(
                "datasheet.not_pdf url=%s content_type=%s", target, content_type
            )
            return None
        if len(content) > _MAX_PDF_BYTES:
            return None
        return content, content_type
    return None


async def acquire(
    quotes: list[SupplierQuote],
    *,
    mpn: str,
    storage: DatasheetStorage,
) -> DatasheetResult:
    """Walk the fallback chain; archive the first valid PDF, else link-only."""

    candidates = _candidate_urls(quotes, mpn)
    if not candidates:
        return DatasheetResult(outcome="none")

    async def _walk() -> DatasheetResult | None:
        for source, url in candidates:
            downloaded = await _try_download(url)
            if downloaded is None:
                continue
            content, content_type = downloaded
            # Storing is best-effort: a storage backend failure (e.g. missing
            # role/SDK) must NOT fail ingestion — fall back to link-only.
            try:
                blob_path = await storage.store(content, content_type=content_type)
            except Exception as exc:
                _log.warning(
                    "datasheet.store_failed mpn=%s source=%s err=%s.%s msg=%s",
                    mpn,
                    source,
                    type(exc).__module__,
                    type(exc).__name__,
                    exc,
                )
                return None
            return DatasheetResult(
                outcome="archived",
                source=source,
                url=_normalize_url(url),
                blob_path=blob_path,
                sha256=sha256_hex(content),
                content_type=content_type,
                size_bytes=len(content),
            )
        return None

    try:
        result = await asyncio.wait_for(_walk(), timeout=_ACQUIRE_BUDGET_SECONDS)
    except TimeoutError:
        _log.warning("datasheet.acquire.budget_exceeded mpn=%s", mpn)
        result = None
    except Exception as exc:  # never let datasheet archival fail ingestion
        _log.warning(
            "datasheet.acquire_failed mpn=%s err=%s.%s msg=%s",
            mpn,
            type(exc).__module__,
            type(exc).__name__,
            exc,
        )
        result = None
    if result is not None:
        return result

    # No PDF downloaded (or budget exceeded) — keep the best-known URL as a link.
    source, url = candidates[0]
    return DatasheetResult(outcome="link_only", source=source, url=_normalize_url(url))
