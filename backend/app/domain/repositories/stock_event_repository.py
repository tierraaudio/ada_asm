"""Repository contract for `StockEvent`."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from app.domain.entities.stock_event import StockEvent


@dataclass
class StockEventPage:
    items: list[StockEvent]
    total: int
    page: int
    page_size: int


class StockEventRepository(Protocol):
    async def list_for_component(
        self,
        *,
        component_id: UUID,
        page: int,
        page_size: int,
    ) -> StockEventPage: ...

    async def save(self, event: StockEvent) -> StockEvent: ...
