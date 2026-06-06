"""Pydantic request / response schemas for the projects + customers surface."""

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
from app.api.v1.schemas.modules import ModuleSummaryResponse

PeriodLiteral = Literal["week", "month", "year"]
ProjectStatusLiteral = Literal[
    "Presupuestado", "Esperando", "En proceso", "Completado", "Archivado"
]


# ----- Customers -----


class CustomerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    holded_id: str
    name: str
    holded_url: str | None = None
    notas: str | None = None
    created_at: datetime
    updated_at: datetime


class CustomerCreateRequest(BaseModel):
    holded_id: Annotated[str, Field(min_length=1, max_length=64)]
    name: Annotated[str, Field(min_length=1, max_length=200)]
    holded_url: Annotated[str | None, Field(default=None, max_length=500)] = None
    notas: str | None = None


class CustomerUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    holded_id: Annotated[str | None, Field(default=None, min_length=1, max_length=64)] = None
    name: Annotated[str | None, Field(default=None, min_length=1, max_length=200)] = None
    holded_url: Annotated[str | None, Field(default=None, max_length=500)] = None
    notas: str | None = None


# ----- Project base + aggregates -----


class ProjectBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    code: str
    name: str
    description: str | None = None
    status: ProjectStatusLiteral
    customer_id: UUID | None = None
    icon: str | None = None
    color: str | None = None
    tags: list[str] = Field(default_factory=list)
    version: str | None = None
    fecha_inicio: date | None = None
    fecha_entrega_estimada: date | None = None
    fecha_entrega_real: date | None = None
    notas: str | None = None
    created_at: datetime
    updated_at: datetime


class ProjectAggregatesPayload(BaseModel):
    precio_total: Decimal | None = None
    aggregated_nato_score: NatoScoreLiteral | None = None
    aggregated_tier: TierLiteral | None = None
    aggregated_expires_at: date | None = None
    buildable_stock: int = 0


class ProjectSummaryResponse(ProjectBase, ProjectAggregatesPayload):
    """Project + aggregates + embedded customer summary.

    Used in list responses, in the "projects-using" surfaces, and as the
    in-tree representation when a project is referenced elsewhere.
    """

    customer: CustomerResponse | None = None


# ----- Children -----


class ProjectChildResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    parent_project_id: UUID
    child_module_id: UUID | None = None
    child_component_id: UUID | None = None
    quantity: int
    sort_order: int
    notes: str | None = None
    child_module: ModuleSummaryResponse | None = None
    child_component: ComponentSummaryResponse | None = None


class ProjectInterestLinkResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    name: str
    url: str
    sort_order: int
    created_at: datetime
    updated_at: datetime


class ProjectInterestLinkCreateRequest(BaseModel):
    name: Annotated[str, Field(min_length=1, max_length=200)]
    url: Annotated[str, Field(min_length=1, max_length=2000)]
    sort_order: int = 0


class ProjectInterestLinkUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: Annotated[str | None, Field(default=None, min_length=1, max_length=200)] = None
    url: Annotated[str | None, Field(default=None, min_length=1, max_length=2000)] = None
    sort_order: int | None = None


class ProjectResponse(ProjectSummaryResponse):
    children: list[ProjectChildResponse] = Field(default_factory=list)
    interest_links: list[ProjectInterestLinkResponse] = Field(default_factory=list)


class PaginatedProjects(BaseModel):
    items: list[ProjectSummaryResponse]
    total: int
    page: int
    page_size: int


# ----- Request bodies -----


class ProjectCreateRequest(BaseModel):
    code: Annotated[str, Field(min_length=1, max_length=40)]
    name: Annotated[str, Field(min_length=1, max_length=200)]
    description: str | None = None
    status: ProjectStatusLiteral = "Presupuestado"
    customer_id: UUID | None = None
    icon: Annotated[str | None, Field(default=None, max_length=8)] = None
    color: Annotated[str | None, Field(default=None, max_length=7)] = None
    tags: list[str] = Field(default_factory=list)
    version: Annotated[str | None, Field(default=None, max_length=40)] = None
    fecha_inicio: date | None = None
    fecha_entrega_estimada: date | None = None
    fecha_entrega_real: date | None = None
    notas: str | None = None


class ProjectUpdateRequest(BaseModel):
    """All fields optional; `id`, `created_at`, `updated_at` ignored if sent."""

    model_config = ConfigDict(extra="ignore")

    code: Annotated[str | None, Field(default=None, min_length=1, max_length=40)] = None
    name: Annotated[str | None, Field(default=None, min_length=1, max_length=200)] = None
    description: str | None = None
    status: ProjectStatusLiteral | None = None
    customer_id: UUID | None = None
    icon: Annotated[str | None, Field(default=None, max_length=8)] = None
    color: Annotated[str | None, Field(default=None, max_length=7)] = None
    tags: list[str] | None = None
    version: Annotated[str | None, Field(default=None, max_length=40)] = None
    fecha_inicio: date | None = None
    fecha_entrega_estimada: date | None = None
    fecha_entrega_real: date | None = None
    notas: str | None = None


class AddProjectChildRequest(BaseModel):
    child_module_id: UUID | None = None
    child_component_id: UUID | None = None
    quantity: Annotated[int, Field(ge=1)] = 1
    notes: str | None = None
    sort_order: int = 0

    @model_validator(mode="after")
    def _xor_child(self) -> AddProjectChildRequest:
        a = self.child_module_id is not None
        b = self.child_component_id is not None
        if a == b:
            raise ValueError("exactly one of child_module_id / child_component_id must be set")
        return self


class UpdateProjectChildRequest(BaseModel):
    quantity: Annotated[int | None, Field(default=None, ge=1)] = None
    notes: str | None = None
    sort_order: int | None = None


# ----- Price history + config -----


class ProjectPriceHistoryPointResponse(BaseModel):
    date: date
    price: Decimal


class ProjectPriceHistoryResponse(BaseModel):
    project_id: UUID
    period: PeriodLiteral
    series: list[ProjectPriceHistoryPointResponse]


class ConfigResponse(BaseModel):
    holded_base_url: str
