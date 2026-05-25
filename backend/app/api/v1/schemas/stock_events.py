"""Pydantic schemas for the stock_events read API."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

StockEventKindLiteral = Literal["purchase", "consumption", "fabricated", "delivered"]


class StockEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    # XOR — exactly one is non-null.
    component_id: UUID | None = None
    module_id: UUID | None = None
    kind: StockEventKindLiteral
    quantity: int
    occurred_at: date
    notes: str | None = None
    # purchase + fabricated economics
    supplier_id: UUID | None = None
    supplier_name: str | None = None  # JOIN with suppliers.name (server-set)
    unit_cost: Decimal | None = None
    total_cost: Decimal | None = None
    currency: str
    # consumption-only
    project_id: UUID | None = None
    project_name_snapshot: str | None = None
    # delivered-only
    customer_id_holded: str | None = None
    customer_name_snapshot: str | None = None
    created_at: datetime
    updated_at: datetime


class PaginatedStockEvents(BaseModel):
    items: list[StockEventResponse]
    total: int
    page: int
    page_size: int


class SupplierPurchaseSummary(BaseModel):
    """Aggregated component-purchase events for a module's descendants.

    Drives the "Proveedor más comprado" bar chart of the module's
    Histórico de Fabricación modal.
    """

    supplier_id: UUID | None = None
    supplier_name: str
    qty: int
    cost: Decimal
