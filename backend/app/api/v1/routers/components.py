"""HTTP routes for the components catalogue."""

from __future__ import annotations

from typing import Annotated, Any, cast
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import get_db_session, require_user
from app.api.v1.schemas.components import (
    ComponentCreateRequest,
    ComponentResponse,
    ComponentUpdateRequest,
    PaginatedComponents,
)
from app.application.services.components_service import (
    _MISSING,
    ComponentCreate,
    ComponentsService,
    ComponentUpdate,
)
from app.domain.entities.component import NatoScoreValue, TierValue
from app.domain.entities.user import User
from app.domain.repositories.component_repository import ComponentFilters
from app.infrastructure.repositories.component_repository import (
    SqlAlchemyComponentRepository,
)

router = APIRouter(prefix="/components", tags=["components"])


def _service(session: AsyncSession) -> ComponentsService:
    return ComponentsService(components=SqlAlchemyComponentRepository(session))


def _payload_to_update(payload: ComponentUpdateRequest) -> ComponentUpdate:
    """Translate a PATCH body into a ComponentUpdate, omitted fields => MISSING."""
    fs = payload.model_fields_set
    d = payload.model_dump()

    def pick(k: str) -> Any:
        return d[k] if k in fs else _MISSING

    return ComponentUpdate(
        sku=pick("sku"),
        name=pick("name"),
        family=pick("family"),
        description=pick("description"),
        datasheet_url=pick("datasheet_url"),
        location=pick("location"),
        fabricante=pick("fabricante"),
        tipo_almacenamiento=pick("tipo_almacenamiento"),
        holded_id=pick("holded_id"),
        fecha_creacion=pick("fecha_creacion"),
        verificado=pick("verificado"),
        notas=pick("notas"),
        stock=pick("stock"),
        stock_min=pick("stock_min"),
        tier=pick("tier"),
        nato_score=pick("nato_score"),
        country_of_origin=pick("country_of_origin"),
        proveedor_preferente_id=pick("proveedor_preferente_id"),
    )


@router.get("", response_model=PaginatedComponents)
async def list_components(
    _user: Annotated[User, Depends(require_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    q: Annotated[str | None, Query()] = None,
    family: Annotated[list[str] | None, Query()] = None,
    supplier_id: Annotated[list[UUID] | None, Query()] = None,
    tier: Annotated[list[int] | None, Query()] = None,
    nato_score: Annotated[list[str] | None, Query()] = None,
    location: Annotated[list[str] | None, Query()] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
) -> PaginatedComponents:
    if tier is not None:
        for t in tier:
            if t not in (1, 2, 3, 4):
                raise HTTPException(status_code=422, detail=f"Invalid tier: {t}")
    if nato_score is not None:
        for s in nato_score:
            if s not in ("A+", "A", "B", "C", "D", "F"):
                raise HTTPException(status_code=422, detail=f"Invalid nato_score: {s}")
    filters = ComponentFilters(
        q=q,
        families=family,
        supplier_ids=supplier_id,
        tiers=cast(list[TierValue] | None, tier),
        nato_scores=cast(list[NatoScoreValue] | None, nato_score),
        locations=location,
    )
    result = await _service(session).list(filters=filters, page=page, page_size=page_size)
    return PaginatedComponents(
        items=[ComponentResponse.model_validate(c) for c in result.items],
        total=result.total,
        page=result.page,
        page_size=result.page_size,
    )


@router.post("", response_model=ComponentResponse, status_code=status.HTTP_201_CREATED)
async def create_component(
    payload: ComponentCreateRequest,
    _user: Annotated[User, Depends(require_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ComponentResponse:
    created = await _service(session).create(
        ComponentCreate(
            mpn=payload.mpn,
            name=payload.name,
            family=payload.family,
            tier=payload.tier,
            nato_score=payload.nato_score,
            sku=payload.sku,
            description=payload.description,
            datasheet_url=payload.datasheet_url,
            location=payload.location,
            fabricante=payload.fabricante,
            tipo_almacenamiento=payload.tipo_almacenamiento,
            holded_id=payload.holded_id,
            fecha_creacion=payload.fecha_creacion,
            verificado=payload.verificado,
            notas=payload.notas,
            stock=payload.stock,
            stock_min=payload.stock_min,
            country_of_origin=payload.country_of_origin,
            proveedor_preferente_id=payload.proveedor_preferente_id,
        )
    )
    return ComponentResponse.model_validate(created)


@router.get("/{component_id}", response_model=ComponentResponse)
async def get_component(
    component_id: UUID,
    _user: Annotated[User, Depends(require_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ComponentResponse:
    component = await _service(session).get(component_id)
    return ComponentResponse.model_validate(component)


@router.patch("/{component_id}", response_model=ComponentResponse)
async def patch_component(
    component_id: UUID,
    payload: ComponentUpdateRequest,
    _user: Annotated[User, Depends(require_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ComponentResponse:
    updated = await _service(session).update(component_id, _payload_to_update(payload))
    return ComponentResponse.model_validate(updated)


@router.delete("/{component_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_component(
    component_id: UUID,
    _user: Annotated[User, Depends(require_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> Response:
    await _service(session).delete(component_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
