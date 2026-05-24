"""Pydantic schemas for supplier prices and supplier stocks read APIs."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class SupplierPriceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    component_id: UUID
    supplier_id: UUID
    qty_tier: int
    price: Decimal
    valid_from: date


class SupplierStockResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    component_id: UUID
    supplier_id: UUID
    quantity: int
    snapshot_at: date
