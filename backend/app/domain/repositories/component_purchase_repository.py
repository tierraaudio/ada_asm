"""Repository contract for `ComponentPurchase`."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from app.domain.entities.component_purchase import ComponentPurchase


@dataclass
class ComponentPurchasePage:
    items: list[ComponentPurchase]
    total: int
    page: int
    page_size: int


class ComponentPurchaseRepository(Protocol):
    async def list_for_component(
        self,
        *,
        component_id: UUID,
        page: int,
        page_size: int,
    ) -> ComponentPurchasePage: ...

    async def save(self, purchase: ComponentPurchase) -> ComponentPurchase: ...
