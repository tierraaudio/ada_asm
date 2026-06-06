"""RS Online / RS Components adapter — stub awaiting credentials.

RS does NOT self-serve API keys. Access requires emailing your RS commercial
representative to receive an App ID; until then this adapter ships
**disabled** and any direct call raises a clear typed error. The registry
(`app/infrastructure/suppliers/registry.py`) gates on credential presence
so the stub is never instantiated in normal operation — but if someone
forces it via `SUPPLIER_SYNC_ENABLED_SUPPLIERS=rs` without a key, this
implementation surfaces a meaningful error instead of an opaque HTTP
failure.

When the App ID arrives:

1. Drop the `NotImplementedError` raise in `fetch_by_mpn`.
2. Implement the REST request against the RS Tactical API (typical
   pattern: `GET https://api.rs-online.com/.../products?searchTerm=<MPN>`
   with the App ID as a header or query parameter).
3. Map response → `SupplierQuote` following the same shape as the other
   four adapters: `mpn` from RS's `mpn` field, `supplier_sku` from RS's
   internal SKU, EUR conversion via `fx.to_eur`.
4. Add fixtures under `tests/fixtures/suppliers/rs/by_mpn/` and unit
   tests parallel to the other adapters.
"""

from __future__ import annotations

from app.core.exceptions import SupplierAuthError
from app.domain.entities.supplier_quote import SupplierCode, SupplierQuote


class RsAdapter:
    """`SupplierAdapter` stub for RS Online — disabled until credentials arrive."""

    code: SupplierCode = "rs"

    def __init__(self, *, api_key: str) -> None:
        self._api_key = api_key

    async def fetch_by_mpn(self, mpn: str) -> SupplierQuote | None:
        # The registry skips this adapter when `RS_API_KEY` is empty, so
        # reaching here implies someone explicitly enabled RS with a key.
        # Until the RS Tactical API endpoint is implemented, surface a
        # typed auth error so the lookup endpoint and sync task record a
        # clear `AUTH_FAILED` event instead of timing out.
        msg = (
            "RS adapter is not yet implemented. "
            "Set RS_API_KEY and replace this stub with a real client once "
            "the RS Tactical API App ID is received."
        )
        raise SupplierAuthError(msg)
