"""HTTP routes for the components catalogue."""

from __future__ import annotations

from typing import Annotated, Any, cast
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import get_db_session, require_user
from app.api.v1.schemas.components import (
    ComponentCreateRequest,
    ComponentDetailResponse,
    ComponentResponse,
    ComponentUpdateRequest,
    CreateNatoScoringRequest,
    NatoScoringResponse,
    NatoScoringSummaryResponse,
    PaginatedComponents,
    ScoringAlternativeResponse,
    ScoringClassificationResponse,
)
from app.application.services.components_service import (
    _MISSING,
    ComponentCreate,
    ComponentsService,
    ComponentUpdate,
)
from app.application.services.nato_scoring_service import (
    AlternativeInput,
    ClassificationInput,
    CreateScoringInput,
    NatoScoringService,
    ScoringBundle,
)
from app.domain.entities.component import NatoScoreValue, TierValue
from app.domain.entities.user import User
from app.domain.repositories.component_repository import ComponentFilters
from app.infrastructure.db.models.user import UserModel
from app.infrastructure.repositories.component_repository import (
    SqlAlchemyComponentRepository,
)
from app.infrastructure.repositories.nato_scoring_repository import (
    SqlAlchemyNatoScoringRepository,
)
from app.infrastructure.repositories.scoring_alternative_repository import (
    SqlAlchemyScoringAlternativeRepository,
)
from app.infrastructure.repositories.scoring_classification_repository import (
    SqlAlchemyScoringClassificationRepository,
)

router = APIRouter(prefix="/components", tags=["components"])


def _service(session: AsyncSession) -> ComponentsService:
    return ComponentsService(components=SqlAlchemyComponentRepository(session))


def _scoring_service(session: AsyncSession) -> NatoScoringService:
    return NatoScoringService(
        session=session,
        components=SqlAlchemyComponentRepository(session),
        scorings=SqlAlchemyNatoScoringRepository(session),
        classifications=SqlAlchemyScoringClassificationRepository(session),
        alternatives=SqlAlchemyScoringAlternativeRepository(session),
    )


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
        notas=pick("notas"),
        stock=pick("stock"),
        stock_min=pick("stock_min"),
        tier=pick("tier"),
        nato_score=pick("nato_score"),
        country_of_origin=pick("country_of_origin"),
        proveedor_preferente_id=pick("proveedor_preferente_id"),
    )


async def _scoring_to_response(session: AsyncSession, bundle: ScoringBundle) -> NatoScoringResponse:
    """Hydrate `classified_by_full_name` with one extra users lookup."""
    full_name: str | None = None
    if bundle.scoring.classified_by_user_id is not None:
        user_row = await session.get(UserModel, bundle.scoring.classified_by_user_id)
        full_name = user_row.full_name if user_row else None
    return NatoScoringResponse(
        id=bundle.scoring.id,
        component_id=cast(UUID, bundle.scoring.component_id),
        nato_score=bundle.scoring.nato_score,
        tier=bundle.scoring.tier,
        classified_at=bundle.scoring.classified_at,
        expires_at=bundle.scoring.expires_at,
        classified_by_user_id=bundle.scoring.classified_by_user_id,
        classified_by_full_name=full_name,
        status=bundle.scoring.status,
        notes=bundle.scoring.notes,
        created_at=cast(Any, bundle.scoring.created_at),
        updated_at=cast(Any, bundle.scoring.updated_at),
        classifications=[
            ScoringClassificationResponse.model_validate(c) for c in bundle.classifications
        ],
        alternatives=[ScoringAlternativeResponse.model_validate(a) for a in bundle.alternatives],
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
            notas=payload.notas,
            stock=payload.stock,
            stock_min=payload.stock_min,
            country_of_origin=payload.country_of_origin,
            proveedor_preferente_id=payload.proveedor_preferente_id,
        )
    )
    return ComponentResponse.model_validate(created)


@router.get("/{component_id}", response_model=ComponentDetailResponse)
async def get_component(
    component_id: UUID,
    _user: Annotated[User, Depends(require_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ComponentDetailResponse:
    component = await _service(session).get(component_id)
    # Hydrate the latest 100u preferred-supplier price (same logic as list).
    await SqlAlchemyComponentRepository(session)._hydrate_current_prices([component])
    bundle = await _scoring_service(session).get_active_bundle(component_id)
    scoring_response: NatoScoringResponse | None = None
    if bundle is not None:
        scoring_response = await _scoring_to_response(session, bundle)
    base = ComponentResponse.model_validate(component).model_dump()
    return ComponentDetailResponse(**base, current_nato_scoring=scoring_response)


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


# ----- NATO scoring sub-resource -----


@router.get(
    "/{component_id}/nato-scorings",
    response_model=list[NatoScoringSummaryResponse],
)
async def list_nato_scorings(
    component_id: UUID,
    user: Annotated[User, Depends(require_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[NatoScoringSummaryResponse]:
    # 404 surfaces explicitly if the component is missing.
    await _service(session).get(component_id)
    scorings = await _scoring_service(session).list_history(component_id)
    if not scorings:
        return []
    # Batch-load user full names for the audit trail.
    user_ids = {s.classified_by_user_id for s in scorings if s.classified_by_user_id}
    users_by_id: dict[UUID, str] = {}
    if user_ids:
        rows = (
            (await session.execute(select(UserModel).where(UserModel.id.in_(user_ids))))
            .scalars()
            .all()
        )
        users_by_id = {row.id: row.full_name for row in rows}
    return [
        NatoScoringSummaryResponse(
            id=s.id,
            component_id=cast(UUID, s.component_id),
            nato_score=s.nato_score,
            tier=s.tier,
            classified_at=s.classified_at,
            expires_at=s.expires_at,
            classified_by_user_id=s.classified_by_user_id,
            classified_by_full_name=(
                users_by_id.get(s.classified_by_user_id) if s.classified_by_user_id else None
            ),
            status=s.status,
            notes=s.notes,
            created_at=cast(Any, s.created_at),
            updated_at=cast(Any, s.updated_at),
        )
        for s in scorings
    ]


@router.post(
    "/{component_id}/nato-scorings",
    response_model=NatoScoringResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_nato_scoring(
    component_id: UUID,
    payload: CreateNatoScoringRequest,
    user: Annotated[User, Depends(require_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> NatoScoringResponse:
    bundle = await _scoring_service(session).create_scoring(
        component_id=component_id,
        payload=CreateScoringInput(
            nato_score=payload.nato_score,
            tier=payload.tier,
            classified_at=payload.classified_at,
            expires_at=payload.expires_at,
            classified_by_user_id=user.id,
            notes=payload.notes,
            classifications=[
                ClassificationInput(
                    part_label=c.part_label,
                    fabricante=c.fabricante,
                    country_of_origin=c.country_of_origin,
                    nato_score=c.nato_score,
                    verificado=c.verificado,
                    notas=c.notas,
                    reference_component_id=c.reference_component_id,
                    reference_url=c.reference_url,
                )
                for c in payload.classifications
            ],
            alternatives=[
                AlternativeInput(
                    alternative_component_id=a.alternative_component_id,
                    notes=a.notes,
                )
                for a in payload.alternatives
            ],
        ),
    )
    return await _scoring_to_response(session, bundle)
