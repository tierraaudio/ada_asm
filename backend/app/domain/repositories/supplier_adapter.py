"""Protocol implemented by every supplier integration.

A `SupplierAdapter` exposes a single async method, `fetch_by_mpn`, used by
both the daily Celery sync and the synchronous `/components/lookup`
endpoint. Each concrete adapter (Mouser, DigiKey, TME, Farnell, RS) lives in
`app/infrastructure/suppliers/<code>.py`. Adapters MUST:

- Return `None` when the supplier responds with "no match" — DO NOT raise.
- Raise a typed `SupplierError` subclass for transport, auth, or parse
  failures so the caller (the sync task or the lookup endpoint) can
  distinguish "supplier said no" from "we couldn't reach the supplier".
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.domain.entities.supplier_quote import SupplierCode, SupplierQuote


@runtime_checkable
class SupplierAdapter(Protocol):
    """Common contract every supplier integration implements."""

    code: SupplierCode

    async def fetch_by_mpn(self, mpn: str) -> SupplierQuote | None:
        """Look up a component by MPN.

        Returns the normalised `SupplierQuote` on a match, or `None` when
        the supplier's API responds with no results (HTTP 404 or empty
        list). MUST raise a `SupplierError` subclass on any non-match
        failure — never swallow transport errors.
        """
        ...
