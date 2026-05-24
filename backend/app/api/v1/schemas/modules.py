"""Pydantic request / response schemas for the modules surface."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.api.v1.schemas.components import (
    ComponentSummaryResponse,
    NatoScoreLiteral,
    TierLiteral,
)

PeriodLiteral = Literal["week", "month", "year"]


class ModuleBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    sku: str
    name: str
    description: str | None = None
    version: str
    fabricante: str | None = None
    location: str | None = None
    tipo_almacenamiento: str | None = None
    stock: int
    notas: str | None = None
    fecha_creacion: date | None = None
    created_at: datetime
    updated_at: datetime


class ModuleAggregatesPayload(BaseModel):
    precio_total: Decimal | None = None
    aggregated_nato_score: NatoScoreLiteral | None = None
    aggregated_tier: TierLiteral | None = None
    aggregated_expires_at: date | None = None
    buildable_stock: int = 0


class ModuleSummaryResponse(ModuleBase, ModuleAggregatesPayload):
    """Used in list responses + as `parents`/`children.child_module` entries."""


class ModuleChildResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    parent_module_id: UUID
    child_module_id: UUID | None = None
    child_component_id: UUID | None = None
    quantity: int
    sort_order: int
    notes: str | None = None
    # Hydrated server-side. Exactly one is non-null per edge (XOR enforced
    # at the DB level).
    child_module: ModuleSummaryResponse | None = None
    child_component: ComponentSummaryResponse | None = None


class ModuleResponse(ModuleBase, ModuleAggregatesPayload):
    children: list[ModuleChildResponse] = Field(default_factory=list)
    parents: list[ModuleSummaryResponse] = Field(default_factory=list)


class PaginatedModules(BaseModel):
    items: list[ModuleSummaryResponse]
    total: int
    page: int
    page_size: int


# ----- Request bodies -----


class ModuleCreateRequest(BaseModel):
    sku: Annotated[str, Field(min_length=1, max_length=100)]
    name: Annotated[str, Field(min_length=1, max_length=200)]
    description: str | None = None
    version: Annotated[str, Field(default="v1.0", max_length=40)] = "v1.0"
    fabricante: Annotated[str | None, Field(default=None, max_length=120)] = None
    location: Annotated[str | None, Field(default=None, max_length=100)] = None
    tipo_almacenamiento: Annotated[str | None, Field(default=None, max_length=80)] = None
    stock: Annotated[int, Field(ge=0)] = 0
    notas: str | None = None
    fecha_creacion: date | None = None


class ModuleUpdateRequest(BaseModel):
    """All fields optional; `id`, `created_at`, `updated_at` ignored if sent."""

    model_config = ConfigDict(extra="ignore")

    sku: Annotated[str | None, Field(default=None, min_length=1, max_length=100)] = None
    name: Annotated[str | None, Field(default=None, min_length=1, max_length=200)] = None
    description: str | None = None
    version: Annotated[str | None, Field(default=None, max_length=40)] = None
    fabricante: Annotated[str | None, Field(default=None, max_length=120)] = None
    location: Annotated[str | None, Field(default=None, max_length=100)] = None
    tipo_almacenamiento: Annotated[str | None, Field(default=None, max_length=80)] = None
    stock: Annotated[int | None, Field(default=None, ge=0)] = None
    notas: str | None = None
    fecha_creacion: date | None = None


class AddChildRequest(BaseModel):
    child_module_id: UUID | None = None
    child_component_id: UUID | None = None
    quantity: Annotated[int, Field(ge=1)] = 1
    notes: str | None = None
    sort_order: int = 0

    @model_validator(mode="after")
    def _xor_child(self) -> AddChildRequest:
        a = self.child_module_id is not None
        b = self.child_component_id is not None
        if a == b:
            raise ValueError("exactly one of child_module_id / child_component_id must be set")
        return self


class UpdateChildRequest(BaseModel):
    quantity: Annotated[int | None, Field(default=None, ge=1)] = None
    notes: str | None = None
    sort_order: int | None = None


class ModulePriceHistoryPointResponse(BaseModel):
    date: date
    price: Decimal


class ModulePriceHistoryResponse(BaseModel):
    module_id: UUID
    period: PeriodLiteral
    series: list[ModulePriceHistoryPointResponse]
