"""Unit tests for ``ComponentsService``.

Cover happy paths and every error branch with a hand-rolled in-memory fake
for the repository protocol.
"""

from __future__ import annotations

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
from app.domain.repositories.component_repository import ComponentFilters, ComponentPage


class FakeComponentRepo:
    def __init__(self) -> None:
        self.by_id: dict[UUID, Component] = {}
        self.list_calls: list[tuple[ComponentFilters, int, int]] = []
        self.saved: list[Component] = []
        self.updated: list[Component] = []
        self.deleted: list[UUID] = []

    async def list(self, *, filters: ComponentFilters, page: int, page_size: int) -> ComponentPage:
        self.list_calls.append((filters, page, page_size))
        items = list(self.by_id.values())
        return ComponentPage(items=items, total=len(items), page=page, page_size=page_size)

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


def _service() -> tuple[ComponentsService, FakeComponentRepo]:
    repo = FakeComponentRepo()
    return ComponentsService(components=cast(object, repo)), repo  # type: ignore[arg-type]


def _sample(**overrides: object) -> Component:
    base = Component(
        mpn="STM32F407VGT6",
        sku="MCU-001",
        name="STM32F407VGT6 - ARM Cortex-M4 MCU",
        family="Microcontroladores",
        tier=1,
        nato_score="A+",
        location="G-A-12",
        fabricante="STMicroelectronics",
        stock=145,
        stock_min=5,
    )
    for k, v in overrides.items():
        setattr(base, k, v)
    return base


# ---------- list ----------


async def test_list_forwards_filters_and_pagination_to_repo() -> None:
    service, repo = _service()
    filters = ComponentFilters(
        q="esp",
        families=["Microcontroladores"],
        tiers=[1, 2],
        nato_scores=["A+", "A"],
    )
    await service.list(filters=filters, page=3, page_size=5)
    assert repo.list_calls == [(filters, 3, 5)]


async def test_list_returns_repository_page() -> None:
    service, repo = _service()
    await repo.save(_sample())
    page = await service.list(filters=ComponentFilters(), page=1, page_size=25)
    assert page.total == 1
    assert page.items[0].mpn == "STM32F407VGT6"


# ---------- get ----------


async def test_get_returns_component_when_found() -> None:
    service, repo = _service()
    component = _sample()
    await repo.save(component)
    fetched = await service.get(component.id)
    assert fetched.id == component.id


async def test_get_raises_not_found_when_missing() -> None:
    service, _ = _service()
    with pytest.raises(ComponentNotFoundError):
        await service.get(uuid4())


# ---------- create ----------


async def test_create_passes_all_fields_to_repo() -> None:
    service, repo = _service()
    created = await service.create(
        ComponentCreate(
            mpn="BME280",
            name="BME280",
            family="Sensores",
            tier=2,
            nato_score="A",
            sku="SEN-008",
            fabricante="Bosch Sensortec",
            stock=12,
            stock_min=4,
            country_of_origin="DE",
        )
    )
    assert created.mpn == "BME280"
    assert repo.saved[0].sku == "SEN-008"
    assert repo.saved[0].fabricante == "Bosch Sensortec"


# ---------- update ----------


async def test_update_only_overrides_provided_fields() -> None:
    service, repo = _service()
    component = _sample()
    await repo.save(component)
    updated = await service.update(component.id, ComponentUpdate(name="Renamed", stock=99))
    assert updated.name == "Renamed"
    assert updated.stock == 99
    assert updated.family == "Microcontroladores"
    assert updated.tier == 1


async def test_update_preserves_mpn_as_immutable() -> None:
    service, repo = _service()
    component = _sample()
    await repo.save(component)
    updated = await service.update(component.id, ComponentUpdate(name="x"))
    assert updated.mpn == "STM32F407VGT6"


async def test_update_allows_setting_nullable_to_none() -> None:
    service, repo = _service()
    component = _sample()
    await repo.save(component)
    updated = await service.update(component.id, ComponentUpdate(description=None))
    assert updated.description is None


async def test_update_raises_not_found_when_missing() -> None:
    service, _ = _service()
    with pytest.raises(ComponentNotFoundError):
        await service.update(uuid4(), ComponentUpdate(name="x"))


# ---------- delete ----------


async def test_delete_calls_repository() -> None:
    service, repo = _service()
    component = _sample()
    await repo.save(component)
    await service.delete(component.id)
    assert repo.deleted == [component.id]


async def test_delete_is_idempotent_on_missing() -> None:
    service, repo = _service()
    missing = uuid4()
    await service.delete(missing)
    assert repo.deleted == [missing]
