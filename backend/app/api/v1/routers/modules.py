"""HTTP routes for the modules catalogue (DAG of assemblies)."""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated, Any, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import get_db_session, require_user
from app.api.v1.schemas.components import ComponentSummaryResponse
from app.api.v1.schemas.modules import (
    AddChildRequest,
    ModuleChildResponse,
    ModuleCreateRequest,
    ModulePriceHistoryPointResponse,
    ModulePriceHistoryResponse,
    ModuleResponse,
    ModuleSummaryResponse,
    ModuleUpdateRequest,
    PaginatedModules,
    PeriodLiteral,
    UpdateChildRequest,
)
from app.api.v1.schemas.stock_events import (
    PaginatedStockEvents,
    StockEventResponse,
    SupplierPurchaseSummary,
)
from app.application.services.modules_service import (
    AddChildInput,
    ModuleCreate,
    ModuleDetailBundle,
    ModuleService,
    ModuleUpdate,
    UpdateChildInput,
)
from app.domain.entities.module import Module, ModuleAggregates
from app.domain.entities.module_child import ModuleChild
from app.domain.entities.user import User
from app.domain.repositories.module_repository import ModuleFilters
from app.infrastructure.db.models.stock_event import StockEventModel
from app.infrastructure.db.models.supplier import SupplierModel
from app.infrastructure.repositories.component_repository import (
    SqlAlchemyComponentRepository,
)
from app.infrastructure.repositories.stock_event_repository import (
    SqlAlchemyStockEventRepository,
)

router = APIRouter(prefix="/modules", tags=["modules"])


def _service(session: AsyncSession) -> ModuleService:
    return ModuleService(session)


def _aggregates_payload(a: ModuleAggregates) -> dict[str, object]:
    return {
        "precio_total": a.precio_total,
        "aggregated_nato_score": a.aggregated_nato_score,
        "aggregated_tier": a.aggregated_tier,
        "aggregated_expires_at": a.aggregated_expires_at,
        "buildable_stock": a.buildable_stock,
    }


def _module_summary(m: Module, agg: ModuleAggregates | None = None) -> ModuleSummaryResponse:
    base = {
        "id": m.id,
        "sku": m.sku,
        "name": m.name,
        "description": m.description,
        "version": m.version,
        "family": m.family,
        "fabricante": m.fabricante,
        "location": m.location,
        "tipo_almacenamiento": m.tipo_almacenamiento,
        "stock": m.stock,
        "notas": m.notas,
        "fecha_creacion": m.fecha_creacion,
        "created_at": m.created_at,
        "updated_at": m.updated_at,
    }
    if agg is None:
        base.update(
            precio_total=None,
            aggregated_nato_score=None,
            aggregated_tier=None,
            aggregated_expires_at=None,
            buildable_stock=0,
        )
    else:
        base.update(_aggregates_payload(agg))
    return ModuleSummaryResponse.model_validate(base)


async def _hydrate_child(session: AsyncSession, child: ModuleChild) -> ModuleChildResponse:
    child_module_summary: ModuleSummaryResponse | None = None
    child_component_summary: ComponentSummaryResponse | None = None

    if child.child_module_id is not None:
        bundle = await _service(session).get_detail(child.child_module_id)
        child_module_summary = _module_summary(bundle.module, bundle.aggregates)
    elif child.child_component_id is not None:
        comp_repo = SqlAlchemyComponentRepository(session)
        comp = await comp_repo.get_by_id(child.child_component_id)
        if comp is not None:
            # Hydrate current price for the summary (same flow as scoring alts).
            await comp_repo._hydrate_current_prices([comp])
            child_component_summary = ComponentSummaryResponse(
                id=comp.id,
                mpn=comp.mpn,
                sku=comp.sku,
                name=comp.name,
                family=comp.family,
                fabricante=comp.fabricante,
                country_of_origin=comp.country_of_origin,
                nato_score=comp.nato_score,
                tier=comp.tier,
                stock=comp.stock,
                current_price_per_100_eur=comp.current_price_per_100_eur,
            )

    return ModuleChildResponse(
        id=child.id,
        parent_module_id=child.parent_module_id,
        child_module_id=child.child_module_id,
        child_component_id=child.child_component_id,
        quantity=child.quantity,
        sort_order=child.sort_order,
        notes=child.notes,
        child_module=child_module_summary,
        child_component=child_component_summary,
    )


async def _bundle_to_response(session: AsyncSession, bundle: ModuleDetailBundle) -> ModuleResponse:
    hydrated_children = [await _hydrate_child(session, c) for c in bundle.children]
    parent_summaries = [_module_summary(p) for p in bundle.parents]
    base = {
        "id": bundle.module.id,
        "sku": bundle.module.sku,
        "name": bundle.module.name,
        "description": bundle.module.description,
        "version": bundle.module.version,
        "family": bundle.module.family,
        "fabricante": bundle.module.fabricante,
        "location": bundle.module.location,
        "tipo_almacenamiento": bundle.module.tipo_almacenamiento,
        "stock": bundle.module.stock,
        "notas": bundle.module.notas,
        "fecha_creacion": bundle.module.fecha_creacion,
        "created_at": bundle.module.created_at,
        "updated_at": bundle.module.updated_at,
        "children": hydrated_children,
        "parents": parent_summaries,
    }
    base.update(_aggregates_payload(bundle.aggregates))
    return ModuleResponse.model_validate(base)


# ============================================================================
# Modules
# ============================================================================


@router.get("", response_model=PaginatedModules)
async def list_modules(
    _user: Annotated[User, Depends(require_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    q: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
) -> PaginatedModules:
    svc = _service(session)
    page_data = await svc.list_modules(filters=ModuleFilters(q=q), page=page, page_size=page_size)
    # Hydrate aggregates for each item (one query per module — cheap given
    # page_size cap = 100). Optimise later if needed.
    items: list[ModuleSummaryResponse] = []
    for m in page_data.items:
        agg = await svc.compute_aggregates(m.id, module_stock=m.stock)
        items.append(_module_summary(m, agg))
    return PaginatedModules(
        items=items, total=page_data.total, page=page_data.page, page_size=page_data.page_size
    )


@router.post("", response_model=ModuleResponse, status_code=status.HTTP_201_CREATED)
async def create_module(
    payload: ModuleCreateRequest,
    _user: Annotated[User, Depends(require_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ModuleResponse:
    svc = _service(session)
    created = await svc.create(
        ModuleCreate(
            sku=payload.sku,
            name=payload.name,
            description=payload.description,
            version=payload.version,
            family=payload.family,
            fabricante=payload.fabricante,
            location=payload.location,
            tipo_almacenamiento=payload.tipo_almacenamiento,
            stock=payload.stock,
            notas=payload.notas,
            fecha_creacion=payload.fecha_creacion,
        )
    )
    bundle = await svc.get_detail(created.id)
    return await _bundle_to_response(session, bundle)


@router.get("/{module_id}", response_model=ModuleResponse)
async def get_module(
    module_id: UUID,
    _user: Annotated[User, Depends(require_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ModuleResponse:
    bundle = await _service(session).get_detail(module_id)
    return await _bundle_to_response(session, bundle)


@router.patch("/{module_id}", response_model=ModuleResponse)
async def patch_module(
    module_id: UUID,
    payload: ModuleUpdateRequest,
    _user: Annotated[User, Depends(require_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ModuleResponse:
    svc = _service(session)
    await svc.update(
        module_id,
        ModuleUpdate(
            sku=payload.sku,
            name=payload.name,
            description=payload.description,
            version=payload.version,
            family=payload.family,
            fabricante=payload.fabricante,
            location=payload.location,
            tipo_almacenamiento=payload.tipo_almacenamiento,
            stock=payload.stock,
            notas=payload.notas,
            fecha_creacion=payload.fecha_creacion,
        ),
    )
    bundle = await svc.get_detail(module_id)
    return await _bundle_to_response(session, bundle)


@router.delete("/{module_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_module(
    module_id: UUID,
    _user: Annotated[User, Depends(require_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> Response:
    await _service(session).delete(module_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ============================================================================
# Children (DAG edges)
# ============================================================================


@router.post(
    "/{module_id}/children",
    response_model=ModuleChildResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_child(
    module_id: UUID,
    payload: AddChildRequest,
    _user: Annotated[User, Depends(require_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ModuleChildResponse:
    child = await _service(session).add_child(
        module_id,
        AddChildInput(
            child_module_id=payload.child_module_id,
            child_component_id=payload.child_component_id,
            quantity=payload.quantity,
            notes=payload.notes,
            sort_order=payload.sort_order,
        ),
    )
    return await _hydrate_child(session, child)


@router.patch(
    "/{module_id}/children/{child_id}",
    response_model=ModuleChildResponse,
)
async def patch_child(
    module_id: UUID,
    child_id: UUID,
    payload: UpdateChildRequest,
    _user: Annotated[User, Depends(require_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ModuleChildResponse:
    child = await _service(session).update_child(
        module_id,
        child_id,
        UpdateChildInput(
            quantity=payload.quantity,
            notes=payload.notes,
            sort_order=payload.sort_order,
        ),
    )
    return await _hydrate_child(session, child)


@router.delete(
    "/{module_id}/children/{child_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_child(
    module_id: UUID,
    child_id: UUID,
    _user: Annotated[User, Depends(require_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> Response:
    await _service(session).remove_child(module_id, child_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ============================================================================
# Price history
# ============================================================================


@router.get(
    "/{module_id}/price-history",
    response_model=ModulePriceHistoryResponse,
)
async def get_price_history(
    module_id: UUID,
    _user: Annotated[User, Depends(require_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    period: PeriodLiteral = "year",
) -> ModulePriceHistoryResponse:
    points = await _service(session).list_price_history(module_id, period=period)
    return ModulePriceHistoryResponse(
        module_id=module_id,
        period=period,
        series=[ModulePriceHistoryPointResponse(date=p.date, price=p.price) for p in points],
    )


# ============================================================================
# Stock events (module-level: fabricated + delivered)
# ============================================================================


@router.get(
    "/{module_id}/stock-events",
    response_model=PaginatedStockEvents,
)
async def list_module_stock_events(
    module_id: UUID,
    _user: Annotated[User, Depends(require_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=200, ge=1, le=500),
) -> PaginatedStockEvents:
    # 404 if the module is missing.
    await _service(session).get(module_id)
    repo = SqlAlchemyStockEventRepository(session)
    page_data = await repo.list_for_module(module_id=module_id, page=page, page_size=page_size)
    # No supplier hydration needed (module-level events don't have suppliers
    # in the canonical case — `fabricated` has no supplier, `delivered`
    # carries customer info already denormalised).
    items = [
        StockEventResponse(
            id=e.id,
            component_id=e.component_id,
            module_id=e.module_id,
            kind=e.kind,
            quantity=e.quantity,
            occurred_at=e.occurred_at,
            notes=e.notes,
            supplier_id=e.supplier_id,
            supplier_name=None,
            unit_cost=e.unit_cost,
            total_cost=e.total_cost,
            currency=e.currency,
            project_id=e.project_id,
            project_name_snapshot=e.project_name_snapshot,
            customer_id_holded=e.customer_id_holded,
            customer_name_snapshot=e.customer_name_snapshot,
            created_at=cast(Any, e.created_at),
            updated_at=cast(Any, e.updated_at),
        )
        for e in page_data.items
    ]
    return PaginatedStockEvents(
        items=items,
        total=page_data.total,
        page=page_data.page,
        page_size=page_data.page_size,
    )


@router.get(
    "/{module_id}/component-purchases-summary",
    response_model=list[SupplierPurchaseSummary],
)
async def get_component_purchases_summary(
    module_id: UUID,
    _user: Annotated[User, Depends(require_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[SupplierPurchaseSummary]:
    """Aggregate component-level purchase events for every descendant
    component of `module_id`, grouped by supplier.

    Drives the "Proveedor más comprado" bar chart of the module's Histórico
    de Fabricación modal.
    """
    svc = _service(session)
    # 404 if missing.
    await svc.get(module_id)

    # Recursively collect descendant components (component_id, propagated_qty).
    descendants = await svc._repo.list_descendant_components(module_id)
    if not descendants:
        return []
    comp_ids = list({c[0] for c in descendants})

    # Aggregate purchase events for those components by supplier.
    rows = (
        await session.execute(
            select(
                StockEventModel.supplier_id,
                SupplierModel.name,
                func.sum(StockEventModel.quantity).label("qty"),
                func.coalesce(func.sum(StockEventModel.total_cost), 0).label("cost"),
            )
            .join(SupplierModel, SupplierModel.id == StockEventModel.supplier_id, isouter=True)
            .where(StockEventModel.component_id.in_(comp_ids))
            .where(StockEventModel.kind == "purchase")
            .group_by(StockEventModel.supplier_id, SupplierModel.name)
            .order_by(func.sum(StockEventModel.total_cost).desc().nullslast())
        )
    ).all()

    return [
        SupplierPurchaseSummary(
            supplier_id=r[0],
            supplier_name=r[1] or "Sin proveedor",
            qty=int(r[2]),
            cost=Decimal(r[3]),
        )
        for r in rows
    ]
