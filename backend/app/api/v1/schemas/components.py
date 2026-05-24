"""Pydantic request / response schemas for the components surface."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

TierLiteral = Literal[1, 2, 3, 4]
NatoScoreLiteral = Literal["A+", "A", "B", "C", "D", "F"]

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
    fabricante: str | None = None
    tipo_almacenamiento: str | None = None
    holded_id: str | None = None
    fecha_creacion: date | None = None
    verificado: bool = False
    notas: str | None = None
    stock: int
    stock_min: int | None = None
    tier: TierLiteral
    nato_score: NatoScoreLiteral
    country_of_origin: CountryCode | None = None
    proveedor_preferente_id: UUID | None = None
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
    fabricante: Annotated[str | None, Field(default=None, max_length=120)] = None
    tipo_almacenamiento: Annotated[str | None, Field(default=None, max_length=80)] = None
    holded_id: Annotated[str | None, Field(default=None, max_length=80)] = None
    fecha_creacion: date | None = None
    verificado: bool = False
    notas: str | None = None
    stock: NonNegativeInt = 0
    stock_min: NonNegativeInt | None = None
    country_of_origin: CountryCode | None = None
    proveedor_preferente_id: UUID | None = None


class ComponentUpdateRequest(BaseModel):
    """All fields optional; `mpn` / `id` / `created_at` / `updated_at` ignored if sent."""

    model_config = ConfigDict(extra="ignore")

    sku: Annotated[str | None, Field(default=None, max_length=100)] = None
    name: Annotated[str | None, Field(default=None, min_length=1, max_length=200)] = None
    family: Annotated[str | None, Field(default=None, min_length=1, max_length=100)] = None
    description: str | None = None
    datasheet_url: str | None = None
    location: Annotated[str | None, Field(default=None, max_length=100)] = None
    fabricante: Annotated[str | None, Field(default=None, max_length=120)] = None
    tipo_almacenamiento: Annotated[str | None, Field(default=None, max_length=80)] = None
    holded_id: Annotated[str | None, Field(default=None, max_length=80)] = None
    fecha_creacion: date | None = None
    verificado: bool | None = None
    notas: str | None = None
    stock: NonNegativeInt | None = None
    stock_min: NonNegativeInt | None = None
    tier: TierLiteral | None = None
    nato_score: NatoScoreLiteral | None = None
    country_of_origin: CountryCode | None = None
    proveedor_preferente_id: UUID | None = None


class PaginatedComponents(BaseModel):
    items: list[ComponentResponse]
    total: int
    page: int
    page_size: int


class SupplierResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
