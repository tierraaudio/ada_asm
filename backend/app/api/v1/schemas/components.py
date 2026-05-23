"""Pydantic request / response schemas for the components surface."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

TierLiteral = Literal["A+", "A", "B", "C", "D"]
NatoScoreLiteral = Literal[
    "100_otan",
    "otan",
    "allied_otan",
    "neutral",
    "high_risk",
    "no_otan",
]

# Common types
NonNegativeInt = Annotated[int, Field(ge=0)]
NonNegativeDecimal = Annotated[Decimal, Field(ge=Decimal("0"))]
CountryCode = Annotated[str, Field(min_length=2, max_length=2, pattern=r"^[A-Z]{2}$")]


class ComponentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    mpn: str
    sku: str | None = None
    name: str
    family: str
    description: str | None = None
    datasheet_url: str | None = None
    location: str | None = None
    supplier: str | None = None
    price_per_100: Decimal | None = None
    stock: int
    tier: TierLiteral
    nato_score: NatoScoreLiteral
    country_of_origin: CountryCode | None = None
    created_at: datetime
    updated_at: datetime


class ComponentCreateRequest(BaseModel):
    mpn: Annotated[str, Field(min_length=1, max_length=100)]
    name: Annotated[str, Field(min_length=1, max_length=200)]
    family: Annotated[str, Field(min_length=1, max_length=100)]
    tier: TierLiteral
    nato_score: NatoScoreLiteral
    sku: Annotated[str | None, Field(default=None, max_length=100)] = None
    description: str | None = None
    datasheet_url: str | None = None
    location: Annotated[str | None, Field(default=None, max_length=100)] = None
    supplier: Annotated[str | None, Field(default=None, max_length=100)] = None
    price_per_100: NonNegativeDecimal | None = None
    stock: NonNegativeInt = 0
    country_of_origin: CountryCode | None = None


class ComponentUpdateRequest(BaseModel):
    """All fields optional; `mpn` / `id` / `created_at` / `updated_at` ignored if sent."""

    model_config = ConfigDict(extra="ignore")

    sku: Annotated[str | None, Field(default=None, max_length=100)] = None
    name: Annotated[str | None, Field(default=None, min_length=1, max_length=200)] = None
    family: Annotated[str | None, Field(default=None, min_length=1, max_length=100)] = None
    description: str | None = None
    datasheet_url: str | None = None
    location: Annotated[str | None, Field(default=None, max_length=100)] = None
    supplier: Annotated[str | None, Field(default=None, max_length=100)] = None
    price_per_100: NonNegativeDecimal | None = None
    stock: NonNegativeInt | None = None
    tier: TierLiteral | None = None
    nato_score: NatoScoreLiteral | None = None
    country_of_origin: CountryCode | None = None


class PaginatedComponents(BaseModel):
    items: list[ComponentResponse]
    total: int
    page: int
    page_size: int


class ComponentPurchaseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    component_id: UUID
    purchased_at: date
    quantity: int
    supplier: str
    unit_cost: Decimal
    total_cost: Decimal
    currency: str
    created_at: datetime


class PaginatedComponentPurchases(BaseModel):
    items: list[ComponentPurchaseResponse]
    total: int
    page: int
    page_size: int


class ComponentSyncResponse(BaseModel):
    status: Literal["queued"] = "queued"
