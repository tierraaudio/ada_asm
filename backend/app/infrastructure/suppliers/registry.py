"""Supplier registry — single source of truth for "which adapters are live".

A supplier is active iff BOTH:

- Its code is listed in `Settings.supplier_sync_enabled_suppliers`, AND
- Its credentials are present in `Settings`.

The first gate is a deploy-time flag (e.g. RS Online ships disabled
until the App ID arrives); the second is a fail-soft — if a key is
missing we silently skip that supplier and log INFO, instead of
crashing the boot process.

Concrete adapter classes live in sibling modules
(`mouser.py`, `digikey.py`, `tme.py`, `farnell.py`, `rs.py`) and are
imported lazily so the registry can be unit-tested without instantiating
every HTTP client.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from app.core.config import Settings, get_settings

if TYPE_CHECKING:
    from app.domain.entities.supplier_quote import SupplierCode
    from app.domain.repositories.supplier_adapter import SupplierAdapter

_log = logging.getLogger(__name__)


def _has_credentials(code: SupplierCode, settings: Settings) -> bool:
    """Per-supplier credential presence check. Keeps the gate's "what counts
    as configured" rule colocated with the registry, NOT scattered across
    the adapters."""

    if code == "mouser":
        return bool(settings.mouser_api_key)
    if code == "digikey":
        return bool(
            settings.digikey_client_id and settings.digikey_client_secret,
        )
    if code == "tme":
        return bool(settings.tme_token and settings.tme_app_secret)
    if code == "farnell":
        return bool(settings.farnell_api_key)
    if code == "rs":
        return bool(settings.rs_api_key)
    return False


def _build_adapter(code: SupplierCode, settings: Settings) -> SupplierAdapter:
    """Lazy import + construct the concrete adapter for `code`."""

    if code == "mouser":
        from app.infrastructure.suppliers.mouser import MouserAdapter

        return MouserAdapter(api_key=settings.mouser_api_key or "")
    if code == "digikey":
        from app.infrastructure.suppliers.digikey import DigiKeyAdapter

        return DigiKeyAdapter(
            client_id=settings.digikey_client_id or "",
            client_secret=settings.digikey_client_secret or "",
            token_url=settings.digikey_oauth_token_url,
        )
    if code == "tme":
        from app.infrastructure.suppliers.tme import TmeAdapter

        return TmeAdapter(
            token=settings.tme_token or "",
            app_secret=settings.tme_app_secret or "",
        )
    if code == "farnell":
        from app.infrastructure.suppliers.farnell import FarnellAdapter

        return FarnellAdapter(
            api_key=settings.farnell_api_key or "",
            store_id=settings.farnell_store_id,
        )
    if code == "rs":
        from app.infrastructure.suppliers.rs import RsAdapter

        return RsAdapter(api_key=settings.rs_api_key or "")
    msg = f"Unknown supplier code: {code}"
    raise ValueError(msg)


def enabled_adapters(
    *,
    settings: Settings | None = None,
) -> list[SupplierAdapter]:
    """Return the active `SupplierAdapter` instances for the daily sync.

    Walks `supplier_sync_enabled_suppliers` and skips any code that has
    no credentials configured. The order in the returned list matches
    the order in the setting so callers can iterate deterministically.
    """

    settings = settings or get_settings()
    out: list[SupplierAdapter] = []
    for code in settings.supplier_sync_enabled_suppliers:
        # The setting is already lowercase + comma-split by the field
        # validator, so plain string comparison is safe here.
        supplier_code: SupplierCode = code  # type: ignore[assignment]
        if not _has_credentials(supplier_code, settings):
            _log.info(
                "supplier.%s.skipped reason=missing_credentials",
                supplier_code,
            )
            continue
        try:
            out.append(_build_adapter(supplier_code, settings))
        except ValueError:
            _log.warning("supplier.%s.skipped reason=unknown_code", supplier_code)
    return out


def lookup_adapters_in_priority_order(
    *,
    settings: Settings | None = None,
) -> list[SupplierAdapter]:
    """Return adapters for the `/components/lookup` endpoint, ordered by
    `supplier_lookup_priority`. Same credential + enabled gates apply.

    Suppliers listed in the priority but NOT in `enabled_suppliers` are
    silently skipped (same as `enabled_adapters`).
    """

    settings = settings or get_settings()
    enabled = set(settings.supplier_sync_enabled_suppliers)
    out: list[SupplierAdapter] = []
    for code in settings.supplier_lookup_priority:
        supplier_code: SupplierCode = code  # type: ignore[assignment]
        if supplier_code not in enabled:
            continue
        if not _has_credentials(supplier_code, settings):
            _log.info(
                "supplier.%s.skipped reason=missing_credentials",
                supplier_code,
            )
            continue
        try:
            out.append(_build_adapter(supplier_code, settings))
        except ValueError:
            _log.warning("supplier.%s.skipped reason=unknown_code", supplier_code)
    return out
