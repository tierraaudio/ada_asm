"""Unit tests for ``ComponentsService``.

Cover happy paths and every error branch with hand-rolled in-memory fakes for
the repository protocols. Filter composition is verified by inspecting what the
service forwards to the repository.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from decimal import Decimal
from typing import cast
from uuid import UUID, uuid4

import pytest

from app.application.services.components_service import (
    ComponentCreate,
    ComponentsService,
    ComponentUpdate,
)
from app.core.exceptions import ComponentNotFoundError
from app.domain.entities.component import Component
from app.domain.entities.component_purchase import ComponentPurchase
from app.domain.repositories.component_purchase_repository import ComponentPurchasePage
from app.domain.repositories.component_repository import ComponentFilters, ComponentPage


class FakeComponentRepo:
    def __init__(self) -> None:
        self.by_id: dict[UUID, Component] = {}
        self.list_calls: list[tuple[ComponentFilters, int, int]] = []
        self.saved: list[Component] = []
        self.updated: list[Component] = []
        self.deleted: list[UUID] = []

    async def list(
        self, *, filters: ComponentFilters, page: int, page_size: int
    ) -> ComponentPage:
        self.list_calls.append((filters, page, page_size))
        items = list(self.by_id.values())
        return ComponentPage(
            items=items, total=len(items), page=page, page_size=page_size
        )

    async def get_by_id(self, component_id: UUID) -> Component | None:
        return self.by_id.get(component_id)

    async def get_by_mpn(self, mpn: str) -> Component | None:
        for c in self.by_id.values():
            if c.mpn.lower() == mpn.lower():
                return c
        return None

    async def save(self, component: Component) -> Component:
        self.saved.append(component)
        self.by_id[component.id] = component
        return component

    async def update(self, component: Component) -> Component:
        self.updated.append(component)
        self.by_id[component.id] = component
        return component

    async def delete(self, component_id: UUID) -> bool:
        self.deleted.append(component_id)
        return self.by_id.pop(component_id, None) is not None


class FakePurchaseRepo:
    def __init__(self) -> None:
        self.by_component: dict[UUID, list[ComponentPurchase]] = {}
        self.list_calls: list[tuple[UUID, int, int]] = []

    async def list_for_component(
        self, *, component_id: UUID, page: int, page_size: int
    ) -> ComponentPurchasePage:
        self.list_calls.append((component_id, page, page_size))
        items = self.by_component.get(component_id, [])
        return ComponentPurchasePage(
            items=items, total=len(items), page=page, page_size=page_size
        )

    async def save(self, purchase: ComponentPurchase) -> ComponentPurchase:
        self.by_component.setdefault(purchase.component_id, []).append(purchase)
        return purchase


def _service() -> tuple[ComponentsService, FakeComponentRepo, FakePurchaseRepo]:
    components = FakeComponentRepo()
    purchases = FakePurchaseRepo()
    return (
        ComponentsService(
            components=cast(object, components),  # type: ignore[arg-type]
            purchases=cast(object, purchases),  # type: ignore[arg-type]
        ),
        components,
        purchases,
    )


def _sample_component(**overrides: object) -> Component:
    base = Component(
        mpn="ACS712",
        sku="ACS712-30A",
        name="Sensor Hall",
        family="Sensores",
        tier="B",
        nato_score="otan",
        country_of_origin="US",
        price_per_100=Decimal("8.4500"),
        stock=10,
    )
    for k, v in overrides.items():
        setattr(base, k, v)
    return base


# ---------- list ----------


async def test_list_forwards_filters_and_pagination_to_repo() -> None:
    service, components, _ = _service()
    filters = ComponentFilters(
        q="hall", family="Sensores", supplier="DigiKey", tier="A", nato_score="otan"
    )
    await service.list(filters=filters, page=3, page_size=5)
    assert components.list_calls == [(filters, 3, 5)]


async def test_list_returns_repository_page() -> None:
    service, components, _ = _service()
    comp = _sample_component()
    await components.save(comp)
    page = await service.list(filters=ComponentFilters(), page=1, page_size=25)
    assert page.total == 1
    assert page.items[0].mpn == "ACS712"


# ---------- get ----------


async def test_get_returns_component_when_found() -> None:
    service, components, _ = _service()
    comp = _sample_component()
    await components.save(comp)
    fetched = await service.get(comp.id)
    assert fetched.id == comp.id


async def test_get_raises_not_found_when_missing() -> None:
    service, _, _ = _service()
    with pytest.raises(ComponentNotFoundError):
        await service.get(uuid4())


# ---------- create ----------


async def test_create_passes_all_fields_to_repo() -> None:
    service, components, _ = _service()
    created = await service.create(
        ComponentCreate(
            mpn="BME280",
            name="Sensor T/H/P",
            family="Sensores",
            tier="B",
            nato_score="allied_otan",
            sku="BME280-X",
            description="d",
            datasheet_url="https://example.com/ds.pdf",
            location="A-1",
            supplier="DigiKey",
            price_per_100=Decimal("4.78"),
            stock=12,
            country_of_origin="JP",
        )
    )
    assert created.mpn == "BME280"
    assert components.saved[0].sku == "BME280-X"
    assert components.saved[0].country_of_origin == "JP"


# ---------- update ----------


async def test_update_only_overrides_provided_fields() -> None:
    service, components, _ = _service()
    comp = _sample_component()
    await components.save(comp)
    updated = await service.update(
        comp.id,
        ComponentUpdate(name="New Name", stock=99),
    )
    assert updated.name == "New Name"
    assert updated.stock == 99
    # Untouched fields preserved
    assert updated.family == "Sensores"
    assert updated.tier == "B"
    assert updated.sku == "ACS712-30A"


async def test_update_preserves_mpn_as_immutable() -> None:
    service, components, _ = _service()
    comp = _sample_component()
    await components.save(comp)
    updated = await service.update(comp.id, ComponentUpdate(name="Renamed"))
    assert updated.mpn == "ACS712"


async def test_update_allows_setting_nullable_field_back_to_none() -> None:
    service, components, _ = _service()
    comp = _sample_component()
    await components.save(comp)
    updated = await service.update(comp.id, ComponentUpdate(description=None))
    assert updated.description is None


async def test_update_raises_not_found_when_missing() -> None:
    service, _, _ = _service()
    with pytest.raises(ComponentNotFoundError):
        await service.update(uuid4(), ComponentUpdate(name="x"))


# ---------- delete ----------


async def test_delete_calls_repository() -> None:
    service, components, _ = _service()
    comp = _sample_component()
    await components.save(comp)
    await service.delete(comp.id)
    assert components.deleted == [comp.id]


async def test_delete_is_idempotent_on_missing() -> None:
    service, components, _ = _service()
    missing = uuid4()
    await service.delete(missing)
    assert components.deleted == [missing]


# ---------- purchases ----------


async def test_list_purchases_404s_when_component_missing() -> None:
    service, _, _ = _service()
    with pytest.raises(ComponentNotFoundError):
        await service.list_purchases(component_id=uuid4(), page=1, page_size=10)


async def test_list_purchases_forwards_to_repo() -> None:
    service, components, purchases = _service()
    comp = _sample_component()
    await components.save(comp)
    await service.list_purchases(component_id=comp.id, page=2, page_size=7)
    assert purchases.list_calls == [(comp.id, 2, 7)]


# ---------- sync (placeholder) ----------


async def test_enqueue_sync_404s_when_component_missing() -> None:
    service, _, _ = _service()
    with pytest.raises(ComponentNotFoundError):
        await service.enqueue_sync(uuid4())


async def test_enqueue_sync_returns_when_component_exists() -> None:
    service, components, _ = _service()
    comp = _sample_component()
    await components.save(comp)
    # Should not raise; placeholder logs and returns
    await service.enqueue_sync(comp.id)


# Mark the whole module as asyncio-friendly.
pytestmark = pytest.mark.asyncio

# Silence unused-import warning for the type alias helper.
_: Callable[..., Awaitable[object]] | None = None
