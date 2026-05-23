"""HTTP routes for the components catalogue."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status

from app.api.v1.dependencies import get_db_session, require_user
from app.api.v1.schemas.components import (
    ComponentCreateRequest,
    ComponentPurchaseResponse,
    ComponentResponse,
    ComponentSyncResponse,
    ComponentUpdateRequest,
    NatoScoreLiteral,
    PaginatedComponentPurchases,
    PaginatedComponents,
    TierLiteral,
)
from app.application.services.components_service import (
    _MISSING,
    ComponentCreate,
    ComponentsService,
    ComponentUpdate,
)
from app.domain.entities.user import User
from app.domain.repositories.component_repository import ComponentFilters
from app.infrastructure.repositories.component_purchase_repository import (
    SqlAlchemyComponentPurchaseRepository,
)
from app.infrastructure.repositories.component_repository import (
    SqlAlchemyComponentRepository,
)
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/components", tags=["components"])


def _service(session: AsyncSession) -> ComponentsService:
    return ComponentsService(
        components=SqlAlchemyComponentRepository(session),
        purchases=SqlAlchemyComponentPurchaseRepository(session),
    )


def _payload_to_update(payload: ComponentUpdateRequest) -> ComponentUpdate:
    """Translate a PATCH body into a ComponentUpdate, leaving omitted fields as MISSING."""
    fields_set = payload.model_fields_set
    dumped = payload.model_dump()
    return ComponentUpdate(
        sku=dumped["sku"] if "sku" in fields_set else _MISSING,
        name=dumped["name"] if "name" in fields_set else _MISSING,
        family=dumped["family"] if "family" in fields_set else _MISSING,
        description=dumped["description"] if "description" in fields_set else _MISSING,
        datasheet_url=dumped["datasheet_url"] if "datasheet_url" in fields_set else _MISSING,
        location=dumped["location"] if "location" in fields_set else _MISSING,
        supplier=dumped["supplier"] if "supplier" in fields_set else _MISSING,
        price_per_100=dumped["price_per_100"] if "price_per_100" in fields_set else _MISSING,
        stock=dumped["stock"] if "stock" in fields_set else _MISSING,
        tier=dumped["tier"] if "tier" in fields_set else _MISSING,
        nato_score=dumped["nato_score"] if "nato_score" in fields_set else _MISSING,
        country_of_origin=dumped["country_of_origin"] if "country_of_origin" in fields_set else _MISSING,
    )


@router.get("", response_model=PaginatedComponents)
async def list_components(
    _user: Annotated[User, Depends(require_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    q: Annotated[str | None, Query()] = None,
    family: Annotated[str | None, Query()] = None,
    supplier: Annotated[str | None, Query()] = None,
    tier: Annotated[TierLiteral | None, Query()] = None,
    nato_score: Annotated[NatoScoreLiteral | None, Query()] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
) -> PaginatedComponents:
    filters = ComponentFilters(
        q=q, family=family, supplier=supplier, tier=tier, nato_score=nato_score
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
            supplier=payload.supplier,
            price_per_100=payload.price_per_100,
            stock=payload.stock,
            country_of_origin=payload.country_of_origin,
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


@router.get(
    "/{component_id}/purchases",
    response_model=PaginatedComponentPurchases,
)
async def list_component_purchases(
    component_id: UUID,
    _user: Annotated[User, Depends(require_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
) -> PaginatedComponentPurchases:
    result = await _service(session).list_purchases(
        component_id=component_id, page=page, page_size=page_size
    )
    return PaginatedComponentPurchases(
        items=[ComponentPurchaseResponse.model_validate(p) for p in result.items],
        total=result.total,
        page=result.page,
        page_size=result.page_size,
    )


@router.post(
    "/{component_id}/sync",
    response_model=ComponentSyncResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def sync_component(
    component_id: UUID,
    _user: Annotated[User, Depends(require_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ComponentSyncResponse:
    await _service(session).enqueue_sync(component_id)
    return ComponentSyncResponse()
