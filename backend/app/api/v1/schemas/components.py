"""Pydantic request / response schemas for the components surface."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

TierLiteral = Literal[1, 2, 3, 4]
NatoScoreLiteral = Literal["A+", "A", "B", "C", "D", "F"]
ScoringStatusLiteral = Literal["active", "archived"]

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
    notas: str | None = None
    stock: int
    stock_min: int | None = None
    tier: TierLiteral
    nato_score: NatoScoreLiteral
    country_of_origin: CountryCode | None = None
    proveedor_preferente_id: UUID | None = None
    created_at: datetime
    updated_at: datetime
    # Server-computed read-only fields.
    current_price_per_100_eur: Decimal | None = None


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


# ----- NATO scoring (per-execution audit trail) -----


class ScoringClassificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    nato_scoring_id: UUID
    part_label: str
    fabricante: str | None = None
    country_of_origin: CountryCode | None = None
    nato_score: NatoScoreLiteral | None = None
    verificado: bool
    notas: str | None = None
    reference_component_id: UUID | None = None
    reference_url: str | None = None
    sort_order: int


class ComponentSummaryResponse(BaseModel):
    """Lightweight subset of `Component` for embedding in cross-references."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    mpn: str
    sku: str | None = None
    name: str
    family: str
    fabricante: str | None = None
    location: str | None = None
    country_of_origin: CountryCode | None = None
    nato_score: NatoScoreLiteral
    tier: TierLiteral
    stock: int
    current_price_per_100_eur: Decimal | None = None


class ScoringAlternativeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    nato_scoring_id: UUID
    alternative_component_id: UUID
    notes: str | None = None
    sort_order: int
    # Hydrated server-side from `components` (+ supplier_prices JOIN for the
    # current 100u price). Null if the referenced component was deleted.
    alternative_component: ComponentSummaryResponse | None = None


class NatoScoringSummaryResponse(BaseModel):
    """Just the scoring envelope (no classifications/alternatives)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    component_id: UUID
    nato_score: NatoScoreLiteral
    tier: TierLiteral
    classified_at: date
    expires_at: date
    classified_by_user_id: UUID | None = None
    classified_by_full_name: str | None = None  # JOIN with users.full_name (server-set)
    status: ScoringStatusLiteral
    notes: str | None = None
    created_at: datetime
    updated_at: datetime


class NatoScoringResponse(NatoScoringSummaryResponse):
    """Scoring envelope + classifications + alternatives."""

    classifications: list[ScoringClassificationResponse] = Field(default_factory=list)
    alternatives: list[ScoringAlternativeResponse] = Field(default_factory=list)


class ComponentDetailResponse(ComponentResponse):
    """Extends ComponentResponse with the current scoring bundle."""

    current_nato_scoring: NatoScoringResponse | None = None


class ClassificationInputRequest(BaseModel):
    part_label: Annotated[str, Field(min_length=1, max_length=200)]
    fabricante: Annotated[str | None, Field(default=None, max_length=120)] = None
    country_of_origin: CountryCode | None = None
    nato_score: NatoScoreLiteral | None = None
    verificado: bool = False
    notas: str | None = None
    reference_component_id: UUID | None = None
    reference_url: str | None = None

    @model_validator(mode="after")
    def _reference_is_mutex(self) -> ClassificationInputRequest:
        if self.reference_component_id is not None and self.reference_url is not None:
            raise ValueError("reference_component_id and reference_url are mutually exclusive")
        return self


class AlternativeInputRequest(BaseModel):
    alternative_component_id: UUID
    notes: str | None = None


class CreateNatoScoringRequest(BaseModel):
    nato_score: NatoScoreLiteral
    tier: TierLiteral
    classified_at: date | None = None  # defaults to today
    expires_at: date | None = None  # defaults to classified_at + 6 months
    notes: str | None = None
    classifications: list[ClassificationInputRequest] = Field(default_factory=list)
    alternatives: list[AlternativeInputRequest] = Field(default_factory=list)
