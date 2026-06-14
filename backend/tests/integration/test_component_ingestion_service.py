"""Integration tests for ComponentIngestionService (orchestration + report)."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
import respx
from sqlalchemy import func, select

from app.application.services import component_lookup_service
from app.application.services.component_ingestion_service import (
    ComponentIngestionService,
)
from app.core.exceptions import (
    ComponentMpnAlreadyRegisteredError,
    ComponentMpnNotFoundError,
    SupplierLookupUnavailableError,
)
from app.domain.entities.supplier_quote import (
    SupplierComplianceCode,
    SupplierParameter,
    SupplierPriceBreak,
    SupplierQuote,
)
from app.infrastructure.datasheet_storage import FilesystemDatasheetStorage
from app.infrastructure.db.models.component_blended import (
    ComponentComplianceModel,
    ComponentDocumentModel,
    ComponentParameterModel,
)
from app.infrastructure.db.session import get_session_factory

pytestmark = pytest.mark.asyncio

_PDF = b"%PDF-1.7 fake"
_DS_URL = "http://www.farnell.com/datasheets/x.pdf"


class _FakeAdapter:
    def __init__(self, code, quote=None, raises=None):
        self.code = code
        self._quote = quote
        self._raises = raises

    async def fetch_by_mpn(self, mpn):
        if self._raises is not None:
            raise self._raises
        return self._quote


def _digikey_quote(mpn: str) -> SupplierQuote:
    return SupplierQuote(
        supplier="digikey",
        mpn=mpn,
        manufacturer="Texas Instruments",
        name="DigiKey name",
        description="DigiKey detailed",
        supplier_category_id="280",  # → Diodos in the seed
        supplier_category_name="Single Diodes",
        datasheet_url=_DS_URL,
        image_url="https://mm.digikey.com/x.jpg",
        lifecycle_status="Active",
        moq=1,
        lead_time_days=42,
        unit_weight_kg=Decimal("0.0002"),
        parameters=(SupplierParameter(label="Voltage", value="16V", key="2074"),),
        compliance=(SupplierComplianceCode(code_type="ECCN", code_value="EAR99"),),
        price_breaks=(
            SupplierPriceBreak(
                quantity=1, price_original=Decimal("0.43"), currency_original="EUR"
            ),
        ),
        supplier_sku="296-X-ND",
        country_of_origin="MX",
        raw_payload={"ManufacturerProductNumber": mpn},
        stock=100,
    )


def _patch(monkeypatch, adapters):
    monkeypatch.setattr(
        component_lookup_service,
        "lookup_adapters_in_priority_order",
        lambda settings=None: adapters,
    )


async def _service(storage):
    factory = get_session_factory()
    session = factory()
    return ComponentIngestionService(session, storage=storage), session


async def test_ingest_creates_component_with_blended_and_report(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    mpn = f"ING-{uuid4().hex[:8].upper()}"
    _patch(monkeypatch, [_FakeAdapter("digikey", quote=_digikey_quote(mpn))])
    storage = FilesystemDatasheetStorage(tmp_path)
    service, session = await _service(storage)
    try:
        with respx.mock() as mock:
            mock.get(_DS_URL).mock(
                return_value=httpx.Response(
                    200, content=_PDF, headers={"content-type": "application/pdf"}
                )
            )
            component, report = await service.ingest(mpn, ubicacion="G-T-23", stock_inicial=50)

        # Component populated + family inferred + SKU auto-generated.
        assert component.family == "Diodos"
        assert component.sku and component.sku.startswith("DIO-")
        assert component.location == "G-T-23"
        # Creation date is stamped at ingest (was null before).
        from datetime import UTC, datetime

        assert component.fecha_creacion == datetime.now(UTC).date()
        assert component.stock == 50
        assert component.country_of_origin == "MX"
        assert component.lead_time_days == 42
        assert component.family_needs_review is False
        assert component.raw_category_id == "280"

        # Blended tables persisted.
        async with factory_session(session) as s:
            params = (
                await s.execute(
                    select(func.count()).select_from(ComponentParameterModel).where(
                        ComponentParameterModel.component_id == component.id
                    )
                )
            ).scalar_one()
            compl = (
                await s.execute(
                    select(func.count()).select_from(ComponentComplianceModel).where(
                        ComponentComplianceModel.component_id == component.id
                    )
                )
            ).scalar_one()
            docs = (
                await s.execute(
                    select(ComponentDocumentModel).where(
                        ComponentDocumentModel.component_id == component.id
                    )
                )
            ).scalars().all()
        assert params == 1
        assert compl == 1
        assert len(docs) == 1 and docs[0].blob_path is not None

        # Report mirrors what was stored.
        assert report.status == "ok"
        assert report.family["inferred"] == "Diodos"
        assert report.family["decided_by"] == "digikey"
        assert report.datasheet["outcome"] == "archived"
        assert report.datasheet["source"] == "digikey"
        assert report.counts["parameters"] == 1
        assert report.counts["compliance_codes"] == 1
        assert report.counts["documents"] == 1
        assert "location" in report.manual_overrides_applied
        assert "family" in report.fields_populated
    finally:
        await session.close()


async def test_ingest_duplicate_mpn_rejected_unless_forced(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    mpn = f"DUP-{uuid4().hex[:8].upper()}"
    _patch(monkeypatch, [_FakeAdapter("digikey", quote=_digikey_quote(mpn))])
    storage = FilesystemDatasheetStorage(tmp_path)
    service, session = await _service(storage)
    try:
        with respx.mock() as mock:
            # Datasheet not important here — let the whole chain miss.
            mock.get(_DS_URL).mock(return_value=httpx.Response(404))
            mock.route(host="www.ti.com").mock(return_value=httpx.Response(404))
            await service.ingest(mpn)
            with pytest.raises(ComponentMpnAlreadyRegisteredError):
                await service.ingest(mpn)
    finally:
        await session.close()


async def test_ingest_unknown_mpn_raises_not_found(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _patch(monkeypatch, [_FakeAdapter("digikey", quote=None)])  # consulted, no match
    service, session = await _service(FilesystemDatasheetStorage(tmp_path))
    try:
        with pytest.raises(ComponentMpnNotFoundError):
            await service.ingest("NOPE-123")
    finally:
        await session.close()


async def test_ingest_all_suppliers_error_raises_unavailable(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from app.core.exceptions import SupplierTransportError

    _patch(
        monkeypatch,
        [_FakeAdapter("digikey", raises=SupplierTransportError("boom"))],
    )
    service, session = await _service(FilesystemDatasheetStorage(tmp_path))
    try:
        with pytest.raises(SupplierLookupUnavailableError):
            await service.ingest("ERR-123")
    finally:
        await session.close()


# Helper: a fresh session context bound to the same engine for read-back.
def factory_session(_existing):
    return get_session_factory()()
