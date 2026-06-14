"""Orchestrate ingesting a component from a manufacturer MPN.

Pipeline: gather supplier quotes → infer family → acquire+archive datasheet
→ build the component (blended scalars + auto SKU + manual overrides) →
persist the component and its per-supplier blended tables → assemble a
structured `IngestionReport`. The component is then picked up by the daily
sync, which accumulates price/stock history. See change
`ingest-component-from-mpn`.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.services import datasheet_service
from app.application.services.component_lookup_service import gather_quotes
from app.application.services.datasheet_service import DatasheetResult
from app.application.services.family_inference_service import (
    FamilyInferenceResult,
    resolve_family,
    sku_prefix_for_family,
)
from app.core.exceptions import ComponentMpnAlreadyRegisteredError
from app.domain.entities.component import Component
from app.domain.entities.supplier_quote import SupplierQuote
from app.infrastructure.datasheet_storage import DatasheetStorage
from app.infrastructure.db.models.component import ComponentModel
from app.infrastructure.db.models.component_blended import (
    ComponentComplianceModel,
    ComponentDocumentModel,
    ComponentParameterModel,
    ComponentSupplierPayloadModel,
)
from app.infrastructure.repositories.component_family_rule_repository import (
    SqlAlchemyComponentFamilyRuleRepository,
)
from app.infrastructure.repositories.component_repository import (
    SqlAlchemyComponentRepository,
)

_log = logging.getLogger(__name__)

# Component scalar fields surfaced in the report's fields_populated/missing.
_REPORTED_FIELDS = (
    "name",
    "description",
    "manufacturer",
    "package",
    "family",
    "datasheet_url",
    "image_url",
    "lifecycle_status",
    "country_of_origin",
    "moq",
    "order_multiple",
    "lead_time_days",
    "unit_weight_kg",
)


@dataclass
class IngestionReport:
    status: str
    mpn: str
    sku: str
    sources_consulted: list[str]
    sources_succeeded: list[str]
    sources_contributed: list[str]
    family: dict[str, Any]
    datasheet: dict[str, Any]
    fields_populated: list[str]
    fields_missing: list[str]
    counts: dict[str, int]
    manual_overrides_applied: list[str]
    warnings: list[str] = field(default_factory=list)


def _first_non_null(quotes: list[SupplierQuote], attr: str) -> Any:
    """First non-null value of `attr` across quotes (priority order)."""

    for quote in quotes:
        value = getattr(quote, attr, None)
        if isinstance(value, str) and not value.strip():
            value = None
        if value is not None:
            return value
    return None


def _derive_country_of_origin(quotes: list[SupplierQuote]) -> str | None:
    direct = _first_non_null(quotes, "country_of_origin")
    if direct is not None:
        return str(direct)
    # Fall back to a country code carried in compliance (Mouser/DigiKey).
    for quote in quotes:
        for code in quote.compliance:
            if code.code_type in ("País de origen", "countryOfOrigin", "CountryOfOrigin"):
                return code.code_value
    return None


class ComponentIngestionService:
    def __init__(self, session: AsyncSession, *, storage: DatasheetStorage) -> None:
        self._session = session
        self._storage = storage
        self._components = SqlAlchemyComponentRepository(session)
        self._rules = SqlAlchemyComponentFamilyRuleRepository(session)

    async def ingest(
        self,
        mpn: str,
        *,
        ubicacion: str | None = None,
        stock_inicial: int | None = None,
        holded_id: str | None = None,
        force: bool = False,
    ) -> tuple[Component, IngestionReport]:
        mpn = mpn.strip()

        # 1. Duplicate guard (409 unless forced).
        existing = await self._components.get_by_mpn(mpn)
        if existing is not None and not force:
            raise ComponentMpnAlreadyRegisteredError(
                f"MPN '{mpn}' is already registered"
            )

        # 2. Gather supplier quotes (raises 404 / 502 per disambiguation).
        quotes, consulted, succeeded = await gather_quotes(mpn)
        contributed = [str(q.supplier) for q in quotes]
        warnings: list[str] = []
        errored = [s for s in consulted if s not in succeeded]
        if errored:
            warnings.append(f"Suppliers errored: {', '.join(errored)}")

        # 3. Infer family (signal-strength resolution, separate from merge).
        rules = await self._rules.list_enabled()
        fam = resolve_family(quotes, rules)
        if fam.needs_review:
            warnings.append("Family could not be inferred; flagged for review")

        # 4. Acquire + archive the datasheet (best-effort).
        ds = await datasheet_service.acquire(quotes, mpn=mpn, storage=self._storage)
        if ds.outcome == "link_only":
            warnings.append("Datasheet stored as external link only (no PDF archived)")
        elif ds.outcome == "none":
            warnings.append("No datasheet found")

        # 5. Build the component (presentation merge + blended + SKU + overrides).
        resolved_mpn = str(_first_non_null(quotes, "mpn") or mpn)
        sku = await self._generate_sku(fam.family)
        manual_overrides: list[str] = []
        location = ubicacion
        if location is not None:
            manual_overrides.append("location")
        stock = stock_inicial if stock_inicial is not None else 0
        if stock_inicial is not None:
            manual_overrides.append("stock")
        if holded_id is not None:
            manual_overrides.append("holded_id")

        unit_weight = _first_non_null(quotes, "unit_weight_kg")
        component = Component(
            mpn=resolved_mpn,
            sku=sku,
            name=str(_first_non_null(quotes, "name") or resolved_mpn),
            family=fam.family or "",
            description=_opt_str(_first_non_null(quotes, "description")),
            fabricante=_opt_str(_first_non_null(quotes, "manufacturer")),
            datasheet_url=ds.url,
            location=location,
            holded_id=holded_id,
            # Stamp the user-facing creation date at ingest (distinct from the
            # created_at timestamp) so the detail page shows it immediately.
            fecha_creacion=datetime.now(UTC).date(),
            stock=stock,
            image_url=_opt_str(_first_non_null(quotes, "image_url")),
            lifecycle_status=_opt_str(_first_non_null(quotes, "lifecycle_status")),
            country_of_origin=_derive_country_of_origin(quotes),
            moq=_opt_int(_first_non_null(quotes, "moq")),
            order_multiple=_opt_int(_first_non_null(quotes, "order_multiple")),
            lead_time_days=_opt_int(_first_non_null(quotes, "lead_time_days")),
            unit_weight_kg=unit_weight if isinstance(unit_weight, Decimal) else None,
            family_inferred_supplier=fam.inferred_supplier,
            family_inferred_match_type=fam.match_type,
            raw_category_id=fam.raw_category_id,
            raw_category_name=fam.raw_category_name,
            raw_tariff_code=fam.raw_tariff_code,
            family_confidence=fam.confidence,
            family_needs_review=fam.needs_review,
        )

        # 6. Persist component + blended tables.
        saved = await self._components.save(component)
        counts = await self._persist_blended(saved.id, quotes, ds)
        await self._session.commit()

        # 7. Assemble the report.
        report = self._build_report(
            component=saved,
            consulted=consulted,
            succeeded=succeeded,
            contributed=contributed,
            fam=fam,
            ds=ds,
            counts=counts,
            manual_overrides=manual_overrides,
            warnings=warnings,
        )
        _log.info(
            "ingest.done mpn=%s sku=%s family=%s datasheet=%s warnings=%d",
            resolved_mpn,
            sku,
            fam.family or "(review)",
            ds.outcome,
            len(warnings),
        )
        return saved, report

    async def _generate_sku(self, family: str | None) -> str:
        prefix = sku_prefix_for_family(family)
        stmt = select(func.count()).where(
            ComponentModel.sku.like(f"{prefix}-%")
        )
        used = (await self._session.execute(stmt)).scalar_one()
        return f"{prefix}-{used + 1:03d}"

    async def _persist_blended(
        self,
        component_id: UUID,
        quotes: list[SupplierQuote],
        ds: DatasheetResult,
    ) -> dict[str, int]:
        counts = {
            "price_breaks": sum(len(q.price_breaks) for q in quotes),
            "supplier_stock_rows": sum(1 for q in quotes if q.stock is not None),
            "parameters": 0,
            "compliance_codes": 0,
            "cross_refs": 0,
            "documents": 0,
        }
        for quote in quotes:
            for param in quote.parameters:
                self._session.add(
                    ComponentParameterModel(
                        component_id=component_id,
                        supplier=quote.supplier,
                        param_key=param.key,
                        param_label=param.label,
                        param_value=param.value,
                        param_unit=param.unit,
                    )
                )
                counts["parameters"] += 1
            for code in quote.compliance:
                self._session.add(
                    ComponentComplianceModel(
                        component_id=component_id,
                        supplier=quote.supplier,
                        code_type=code.code_type,
                        code_value=code.code_value,
                    )
                )
                counts["compliance_codes"] += 1
            if quote.raw_payload is not None:
                self._session.add(
                    ComponentSupplierPayloadModel(
                        component_id=component_id,
                        supplier=quote.supplier,
                        raw_payload=quote.raw_payload,
                    )
                )
        if ds.outcome in ("archived", "link_only") and ds.url:
            self._session.add(
                ComponentDocumentModel(
                    component_id=component_id,
                    supplier=ds.source,
                    doc_type="datasheet",
                    url=ds.url,
                    blob_path=ds.blob_path,
                    sha256=ds.sha256,
                    content_type=ds.content_type,
                    size_bytes=ds.size_bytes,
                    fetched_at=func.now() if ds.outcome == "archived" else None,
                )
            )
            counts["documents"] += 1
        return counts

    def _build_report(
        self,
        *,
        component: Component,
        consulted: list[str],
        succeeded: list[str],
        contributed: list[str],
        fam: FamilyInferenceResult,
        ds: DatasheetResult,
        counts: dict[str, int],
        manual_overrides: list[str],
        warnings: list[str],
    ) -> IngestionReport:
        populated: list[str] = []
        missing: list[str] = []
        for name in _REPORTED_FIELDS:
            value = getattr(component, name, None)
            if value in (None, "", 0) and name not in ("moq", "order_multiple"):
                missing.append(name)
            else:
                populated.append(name)
        return IngestionReport(
            status="ok_with_warnings" if warnings else "ok",
            mpn=component.mpn,
            sku=component.sku or "",
            sources_consulted=consulted,
            sources_succeeded=succeeded,
            sources_contributed=contributed,
            family={
                "inferred": fam.family,
                "needs_review": fam.needs_review,
                "decided_by": fam.inferred_supplier,
                "match_type": fam.match_type,
                "raw_category": fam.raw_category_name or fam.raw_category_id,
                "confidence": fam.confidence,
            },
            datasheet={
                "outcome": ds.outcome,
                "source": ds.source,
                "url": ds.url,
                "blob_path": ds.blob_path,
                "size_bytes": ds.size_bytes,
            },
            fields_populated=populated,
            fields_missing=missing,
            counts=counts,
            manual_overrides_applied=manual_overrides,
            warnings=warnings,
        )


def _opt_str(value: object | None) -> str | None:
    return str(value) if value is not None else None


def _opt_int(value: object | None) -> int | None:
    if value is None:
        return None
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return None
