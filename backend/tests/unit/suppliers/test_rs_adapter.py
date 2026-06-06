"""Unit tests for the RS Online stub adapter."""

from __future__ import annotations

import pytest

from app.core.exceptions import SupplierAuthError
from app.infrastructure.suppliers.rs import RsAdapter

pytestmark = pytest.mark.asyncio


def test_adapter_satisfies_protocol() -> None:
    from app.domain.repositories.supplier_adapter import SupplierAdapter

    inst = RsAdapter(api_key="placeholder")
    assert isinstance(inst, SupplierAdapter)
    assert inst.code == "rs"


async def test_fetch_raises_auth_until_real_implementation_arrives() -> None:
    """Until the RS Tactical API client is implemented, every direct call
    MUST surface a typed `SupplierAuthError` so the sync task records a
    meaningful audit event instead of silently failing."""
    adapter = RsAdapter(api_key="placeholder")
    with pytest.raises(SupplierAuthError, match="not yet implemented"):
        await adapter.fetch_by_mpn("anything")
