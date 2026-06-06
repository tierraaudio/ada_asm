"""Pydantic schemas for the `/components/lookup` endpoint."""

from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

SupplierCodeLiteral = Literal["mouser", "digikey", "tme", "farnell", "rs"]


class SupplierPriceBreakResponse(BaseModel):
    """One quantity tier in a supplier's price ladder."""

    model_config = ConfigDict(extra="forbid")

    quantity: int = Field(..., ge=1)
    price_original: Decimal
    currency_original: str = Field(..., min_length=3, max_length=3)
    price_eur: Decimal | None = None


class SupplierData(BaseModel):
    """The raw quote returned by ONE supplier. The lookup endpoint
    preserves every consulted supplier's quote here so the FE can render
    a per-supplier breakdown alongside the merged headline."""

    model_config = ConfigDict(extra="forbid")

    supplier: SupplierCodeLiteral
    supplier_sku: str | None = None
    supplier_product_url: str | None = None
    stock: int | None = None
    price_breaks: list[SupplierPriceBreakResponse] = Field(default_factory=list)


class LookupFields(BaseModel):
    """The merged "headline" view used to pre-fill the new-component
    form. Each field is the first non-null value found in priority
    order across the consulted suppliers."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    description: str | None = None
    manufacturer: str | None = None
    family_hint: str | None = None
    datasheet_url: str | None = None
    package: str | None = None
    current_price_per_100_eur: Decimal | None = None


class LookupResponse(BaseModel):
    """Top-level payload returned by `GET /api/v1/components/lookup`."""

    model_config = ConfigDict(extra="forbid")

    mpn: str
    found: bool
    fields: LookupFields
    supplier_data: list[SupplierData] = Field(default_factory=list)
    sources_consulted: list[SupplierCodeLiteral] = Field(default_factory=list)
    sources_succeeded: list[SupplierCodeLiteral] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)
