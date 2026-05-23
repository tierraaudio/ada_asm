"""Component catalogue service — orchestration layer between API and domain."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any
from uuid import UUID

import structlog

from app.core.exceptions import ComponentNotFoundError
from app.domain.entities.component import Component, NatoScoreValue, TierValue
from app.domain.repositories.component_purchase_repository import (
    ComponentPurchasePage,
    ComponentPurchaseRepository,
)
from app.domain.repositories.component_repository import (
    ComponentFilters,
    ComponentPage,
    ComponentRepository,
)

logger = structlog.get_logger(__name__)


@dataclass
class ComponentCreate:
    mpn: str
    name: str
    family: str
    tier: TierValue
    nato_score: NatoScoreValue
    sku: str | None = None
    description: str | None = None
    datasheet_url: str | None = None
    location: str | None = None
    supplier: str | None = None
    price_per_100: Decimal | None = None
    stock: int = 0
    country_of_origin: str | None = None


class _MissingSentinel:
    """Type for `_MISSING` — a single instance signals "field not provided"."""

    _instance: "_MissingSentinel | None" = None

    def __new__(cls) -> "_MissingSentinel":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __repr__(self) -> str:  # pragma: no cover
        return "<MISSING>"


# Sentinel used to distinguish "field not provided" from "field set to None".
_MISSING: _MissingSentinel = _MissingSentinel()


@dataclass
class ComponentUpdate:
    sku: str | None | _MissingSentinel = _MISSING
    name: str | _MissingSentinel = _MISSING
    family: str | _MissingSentinel = _MISSING
    description: str | None | _MissingSentinel = _MISSING
    datasheet_url: str | None | _MissingSentinel = _MISSING
    location: str | None | _MissingSentinel = _MISSING
    supplier: str | None | _MissingSentinel = _MISSING
    price_per_100: Decimal | None | _MissingSentinel = _MISSING
    stock: int | _MissingSentinel = _MISSING
    tier: TierValue | _MissingSentinel = _MISSING
    nato_score: NatoScoreValue | _MissingSentinel = _MISSING
    country_of_origin: str | None | _MissingSentinel = _MISSING


class ComponentsService:
    def __init__(
        self,
        *,
        components: ComponentRepository,
        purchases: ComponentPurchaseRepository,
    ) -> None:
        self._components = components
        self._purchases = purchases

    async def list(
        self,
        *,
        filters: ComponentFilters,
        page: int = 1,
        page_size: int = 25,
    ) -> ComponentPage:
        return await self._components.list(filters=filters, page=page, page_size=page_size)

    async def get(self, component_id: UUID) -> Component:
        component = await self._components.get_by_id(component_id)
        if component is None:
            raise ComponentNotFoundError(f"Component {component_id} not found")
        return component

    async def create(self, payload: ComponentCreate) -> Component:
        component = Component(
            mpn=payload.mpn,
            sku=payload.sku,
            name=payload.name,
            family=payload.family,
            description=payload.description,
            datasheet_url=payload.datasheet_url,
            location=payload.location,
            supplier=payload.supplier,
            price_per_100=payload.price_per_100,
            stock=payload.stock,
            tier=payload.tier,
            nato_score=payload.nato_score,
            country_of_origin=payload.country_of_origin,
        )
        return await self._components.save(component)

    async def update(self, component_id: UUID, payload: ComponentUpdate) -> Component:
        existing = await self.get(component_id)

        def _apply(current: Any, candidate: Any) -> Any:
            return candidate if candidate is not _MISSING else current

        merged = Component(
            id=existing.id,
            mpn=existing.mpn,  # immutable
            sku=_apply(existing.sku, payload.sku),
            name=_apply(existing.name, payload.name),
            family=_apply(existing.family, payload.family),
            description=_apply(existing.description, payload.description),
            datasheet_url=_apply(existing.datasheet_url, payload.datasheet_url),
            location=_apply(existing.location, payload.location),
            supplier=_apply(existing.supplier, payload.supplier),
            price_per_100=_apply(existing.price_per_100, payload.price_per_100),
            stock=_apply(existing.stock, payload.stock),
            tier=_apply(existing.tier, payload.tier),
            nato_score=_apply(existing.nato_score, payload.nato_score),
            country_of_origin=_apply(existing.country_of_origin, payload.country_of_origin),
            created_at=existing.created_at,
            updated_at=existing.updated_at,
        )
        return await self._components.update(merged)

    async def delete(self, component_id: UUID) -> None:
        # Idempotent: silently no-op when the row does not exist.
        await self._components.delete(component_id)

    async def list_purchases(
        self,
        *,
        component_id: UUID,
        page: int = 1,
        page_size: int = 25,
    ) -> ComponentPurchasePage:
        # 404 surfaces explicitly when the parent component does not exist.
        await self.get(component_id)
        return await self._purchases.list_for_component(
            component_id=component_id, page=page, page_size=page_size
        )

    async def enqueue_sync(self, component_id: UUID) -> None:
        # Resolve the component first so a missing id surfaces 404 to the API.
        component = await self.get(component_id)
        logger.info(
            "components.sync.placeholder",
            component_id=str(component.id),
            mpn=component.mpn,
            dev_only=True,
        )
