"""HTTP routes for the projects catalogue (top of the asset tree)."""

from __future__ import annotations

from typing import Annotated, Any, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import get_db_session, require_user
from app.api.v1.routers.modules import _module_summary
from app.api.v1.schemas.components import ComponentSummaryResponse, SupplierStockSummaryEntry
from app.api.v1.schemas.projects import (
    AddProjectChildRequest,
    CustomerResponse,
    PaginatedProjects,
    PeriodLiteral,
    ProjectChildResponse,
    ProjectCreateRequest,
    ProjectInterestLinkCreateRequest,
    ProjectInterestLinkResponse,
    ProjectInterestLinkUpdateRequest,
    ProjectPriceHistoryPointResponse,
    ProjectPriceHistoryResponse,
    ProjectResponse,
    ProjectStatusLiteral,
    ProjectSummaryResponse,
    ProjectUpdateRequest,
    UpdateProjectChildRequest,
)
from app.api.v1.schemas.stock_events import PaginatedStockEvents, StockEventResponse
from app.application.services.projects_service import (
    AddProjectChildInput,
    ProjectCreate,
    ProjectDetailBundle,
    ProjectService,
    ProjectUpdate,
    UpdateProjectChildInput,
)
from app.domain.entities.customer import Customer
from app.domain.entities.project import Project, ProjectAggregates
from app.domain.entities.project_child import ProjectChild
from app.domain.entities.user import User
from app.domain.repositories.project_repository import ProjectFilters
from app.infrastructure.db.models.supplier import SupplierModel
from app.infrastructure.repositories.component_repository import (
    SqlAlchemyComponentRepository,
)
from app.infrastructure.repositories.customer_repository import SqlAlchemyCustomerRepository
from app.infrastructure.repositories.module_repository import SqlAlchemyModuleRepository
from app.infrastructure.repositories.project_interest_link_repository import (
    SqlAlchemyProjectInterestLinkRepository,
)
from app.infrastructure.repositories.project_repository import SqlAlchemyProjectRepository
from app.infrastructure.repositories.stock_event_repository import (
    SqlAlchemyStockEventRepository,
)
from app.infrastructure.repositories.supplier_stock_repository import (
    SqlAlchemySupplierStockRepository,
)

router = APIRouter(prefix="/projects", tags=["projects"])


# ============================================================================
# Helpers
# ============================================================================


def _service(session: AsyncSession) -> ProjectService:
    return ProjectService(session)


def _aggregates_payload(a: ProjectAggregates) -> dict[str, Any]:
    return {
        "precio_total": a.precio_total,
        "aggregated_nato_score": a.aggregated_nato_score,
        "aggregated_tier": a.aggregated_tier,
        "aggregated_expires_at": a.aggregated_expires_at,
        "buildable_stock": a.buildable_stock,
    }


def _project_base_dict(p: Project) -> dict[str, Any]:
    return {
        "id": p.id,
        "code": p.code,
        "name": p.name,
        "description": p.description,
        "status": p.status,
        "customer_id": p.customer_id,
        "icon": p.icon,
        "color": p.color,
        "tags": list(p.tags),
        "version": p.version,
        "fecha_inicio": p.fecha_inicio,
        "fecha_entrega_estimada": p.fecha_entrega_estimada,
        "fecha_entrega_real": p.fecha_entrega_real,
        "notas": p.notas,
        "created_at": p.created_at,
        "updated_at": p.updated_at,
    }


def _project_summary(
    p: Project,
    *,
    agg: ProjectAggregates | None = None,
    customer: Customer | None = None,
) -> ProjectSummaryResponse:
    base = _project_base_dict(p)
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
    base["customer"] = (
        CustomerResponse.model_validate(customer).model_dump() if customer is not None else None
    )
    return ProjectSummaryResponse.model_validate(base)


async def _hydrate_child(
    session: AsyncSession, child: ProjectChild
) -> ProjectChildResponse:
    """Build a ProjectChildResponse with the right summary embedded.

    - Module child: hydrated via `_module_summary` (reused from modules router)
      with aggregates computed for that module.
    - Component child: hydrated via the components repo with `_hydrate_current_prices`
      + the latest `supplier_stock_summary` (matches the modules surface).
    """
    child_module_summary = None
    child_component_summary = None

    if child.child_module_id is not None:
        # Reuse the modules service to compute the module aggregates so the
        # row matches the canonical ModuleSummary shape.
        from app.application.services.modules_service import ModuleService

        mod_svc = ModuleService(session)
        bundle = await mod_svc.get_detail(child.child_module_id)
        child_module_summary = _module_summary(bundle.module, bundle.aggregates)
    elif child.child_component_id is not None:
        comp_repo = SqlAlchemyComponentRepository(session)
        comp = await comp_repo.get_by_id(child.child_component_id)
        if comp is not None:
            await comp_repo._hydrate_current_prices([comp])
            stock_repo = SqlAlchemySupplierStockRepository(session)
            summary_by_component = await stock_repo.latest_summary_for_components([comp.id])
            child_component_summary = ComponentSummaryResponse(
                id=comp.id,
                mpn=comp.mpn,
                sku=comp.sku,
                name=comp.name,
                family=comp.family,
                fabricante=comp.fabricante,
                location=comp.location,
                country_of_origin=comp.country_of_origin,
                nato_score=comp.nato_score,
                tier=comp.tier,
                stock=comp.stock,
                current_price_per_100_eur=comp.current_price_per_100_eur,
                supplier_stock_summary=[
                    SupplierStockSummaryEntry(
                        supplier_id=sid, supplier_name=sname, quantity=qty
                    )
                    for sid, sname, qty in summary_by_component.get(comp.id, [])
                ],
            )

    return ProjectChildResponse(
        id=child.id,
        parent_project_id=child.parent_project_id,
        child_module_id=child.child_module_id,
        child_component_id=child.child_component_id,
        quantity=child.quantity,
        sort_order=child.sort_order,
        notes=child.notes,
        child_module=child_module_summary,
        child_component=child_component_summary,
    )


async def _bundle_to_response(
    session: AsyncSession, bundle: ProjectDetailBundle
) -> ProjectResponse:
    hydrated_children = [await _hydrate_child(session, c) for c in bundle.children]
    base = _project_base_dict(bundle.project)
    base.update(_aggregates_payload(bundle.aggregates))
    base["customer"] = (
        CustomerResponse.model_validate(bundle.customer).model_dump()
        if bundle.customer is not None
        else None
    )
    base["children"] = hydrated_children
    base["interest_links"] = [
        ProjectInterestLinkResponse.model_validate(li).model_dump()
        for li in bundle.interest_links
    ]
    return ProjectResponse.model_validate(base)


def _patch_to_update(payload: ProjectUpdateRequest) -> tuple[ProjectUpdate, bool]:
    """Translate the request body into a ProjectUpdate.

    Returns (update, explicit_fecha_entrega_real) — the second value tells the
    service whether `fecha_entrega_real` was explicitly part of the request
    body (so the Delivered auto-fill knows when to kick in).
    """
    fs = payload.model_fields_set
    update = ProjectUpdate(
        code=payload.code if "code" in fs else None,
        name=payload.name if "name" in fs else None,
        description=payload.description if "description" in fs else None,
        status=payload.status if "status" in fs else None,
        customer_id=payload.customer_id if "customer_id" in fs else None,
        icon=payload.icon if "icon" in fs else None,
        color=payload.color if "color" in fs else None,
        tags=list(payload.tags) if "tags" in fs and payload.tags is not None else None,
        version=payload.version if "version" in fs else None,
        fecha_inicio=payload.fecha_inicio if "fecha_inicio" in fs else None,
        fecha_entrega_estimada=(
            payload.fecha_entrega_estimada if "fecha_entrega_estimada" in fs else None
        ),
        fecha_entrega_real=(
            payload.fecha_entrega_real if "fecha_entrega_real" in fs else None
        ),
        notas=payload.notas if "notas" in fs else None,
    )
    return update, "fecha_entrega_real" in fs


async def _hydrate_summary_with_customer(
    session: AsyncSession, project: Project, *, agg: ProjectAggregates | None
) -> ProjectSummaryResponse:
    customer = None
    if project.customer_id is not None:
        customer = await SqlAlchemyCustomerRepository(session).get_by_id(project.customer_id)
    return _project_summary(project, agg=agg, customer=customer)


# ============================================================================
# Endpoints
# ============================================================================


@router.get("", response_model=PaginatedProjects)
async def list_projects(
    _user: Annotated[User, Depends(require_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    q: Annotated[str | None, Query()] = None,
    status_: Annotated[list[ProjectStatusLiteral] | None, Query(alias="status")] = None,
    include_archived: Annotated[bool, Query()] = False,
    customer_id: Annotated[list[UUID] | None, Query()] = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
) -> PaginatedProjects:
    svc = _service(session)
    filters = ProjectFilters(
        q=q,
        statuses=list(status_) if status_ else None,
        include_archived=include_archived,
        customer_ids=list(customer_id) if customer_id else [],
    )
    page_data = await svc.list_projects(filters=filters, page=page, page_size=page_size)

    items: list[ProjectSummaryResponse] = []
    for p in page_data.items:
        agg = await svc.compute_aggregates(p.id)
        items.append(await _hydrate_summary_with_customer(session, p, agg=agg))
    return PaginatedProjects(
        items=items,
        total=page_data.total,
        page=page_data.page,
        page_size=page_data.page_size,
    )


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    payload: ProjectCreateRequest,
    _user: Annotated[User, Depends(require_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ProjectResponse:
    svc = _service(session)
    created = await svc.create(
        ProjectCreate(
            code=payload.code,
            name=payload.name,
            description=payload.description,
            status=payload.status,
            customer_id=payload.customer_id,
            icon=payload.icon,
            color=payload.color,
            tags=list(payload.tags),
            version=payload.version,
            fecha_inicio=payload.fecha_inicio,
            fecha_entrega_estimada=payload.fecha_entrega_estimada,
            fecha_entrega_real=payload.fecha_entrega_real,
            notas=payload.notas,
        )
    )
    bundle = await svc.get_detail(created.id)
    return await _bundle_to_response(session, bundle)


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: UUID,
    _user: Annotated[User, Depends(require_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ProjectResponse:
    bundle = await _service(session).get_detail(project_id)
    return await _bundle_to_response(session, bundle)


@router.patch("/{project_id}", response_model=ProjectResponse)
async def patch_project(
    project_id: UUID,
    payload: ProjectUpdateRequest,
    _user: Annotated[User, Depends(require_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ProjectResponse:
    svc = _service(session)
    update, explicit = _patch_to_update(payload)
    await svc.update(project_id, update, explicit_fecha_entrega_real=explicit)
    bundle = await svc.get_detail(project_id)
    return await _bundle_to_response(session, bundle)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: UUID,
    _user: Annotated[User, Depends(require_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> Response:
    """Soft-delete: transitions status to `Archived`."""
    await _service(session).soft_delete(project_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ----- children -----


@router.post(
    "/{project_id}/children",
    response_model=ProjectChildResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_project_child(
    project_id: UUID,
    payload: AddProjectChildRequest,
    _user: Annotated[User, Depends(require_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ProjectChildResponse:
    svc = _service(session)
    created = await svc.add_child(
        project_id,
        AddProjectChildInput(
            child_module_id=payload.child_module_id,
            child_component_id=payload.child_component_id,
            quantity=payload.quantity,
            notes=payload.notes,
            sort_order=payload.sort_order,
        ),
    )
    return await _hydrate_child(session, created)


@router.patch(
    "/{project_id}/children/{child_id}",
    response_model=ProjectChildResponse,
)
async def patch_project_child(
    project_id: UUID,
    child_id: UUID,
    payload: UpdateProjectChildRequest,
    _user: Annotated[User, Depends(require_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ProjectChildResponse:
    svc = _service(session)
    updated = await svc.update_child(
        project_id,
        child_id,
        UpdateProjectChildInput(
            quantity=payload.quantity,
            notes=payload.notes,
            sort_order=payload.sort_order,
        ),
    )
    return await _hydrate_child(session, updated)


@router.delete(
    "/{project_id}/children/{child_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_project_child(
    project_id: UUID,
    child_id: UUID,
    _user: Annotated[User, Depends(require_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> Response:
    await _service(session).remove_child(project_id, child_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ----- price history + stock events -----


@router.get(
    "/{project_id}/price-history",
    response_model=ProjectPriceHistoryResponse,
)
async def project_price_history(
    project_id: UUID,
    _user: Annotated[User, Depends(require_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    period: Annotated[PeriodLiteral, Query()] = "year",
) -> ProjectPriceHistoryResponse:
    svc = _service(session)
    series = await svc.list_price_history(project_id, period=period)
    return ProjectPriceHistoryResponse(
        project_id=project_id,
        period=period,
        series=[
            ProjectPriceHistoryPointResponse(date=p.date, price=p.price) for p in series
        ],
    )


@router.get(
    "/{project_id}/stock-events",
    response_model=PaginatedStockEvents,
)
async def list_project_stock_events(
    project_id: UUID,
    _user: Annotated[User, Depends(require_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200)] = 50,
) -> PaginatedStockEvents:
    """All stock_events tied to this project (consumption + future delivered)."""
    # 404 if project missing.
    await _service(session).get(project_id)

    repo = SqlAlchemyStockEventRepository(session)
    page_data = await repo.list_for_project(
        project_id=project_id, page=page, page_size=page_size
    )

    supplier_ids = {e.supplier_id for e in page_data.items if e.supplier_id is not None}
    suppliers_by_id: dict[UUID, str] = {}
    if supplier_ids:
        rows = (
            (await session.execute(select(SupplierModel).where(SupplierModel.id.in_(supplier_ids))))
            .scalars()
            .all()
        )
        suppliers_by_id = {row.id: row.name for row in rows}
    items = [
        StockEventResponse(
            id=e.id,
            component_id=e.component_id,
            kind=e.kind,
            quantity=e.quantity,
            occurred_at=e.occurred_at,
            notes=e.notes,
            supplier_id=e.supplier_id,
            supplier_name=suppliers_by_id.get(e.supplier_id) if e.supplier_id else None,
            unit_cost=e.unit_cost,
            total_cost=e.total_cost,
            currency=e.currency,
            project_id=e.project_id,
            project_name_snapshot=e.project_name_snapshot,
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


# ============================================================================
# Cross-feature "projects-using" helpers — exposed for reuse from the
# components + modules routers via simple imports.
# ============================================================================


async def list_projects_using_component(
    session: AsyncSession, component_id: UUID
) -> list[ProjectSummaryResponse]:
    svc = _service(session)
    projects = await SqlAlchemyProjectRepository(session).list_for_component(component_id)
    out: list[ProjectSummaryResponse] = []
    for p in projects:
        agg = await svc.compute_aggregates(p.id)
        out.append(await _hydrate_summary_with_customer(session, p, agg=agg))
    return out


async def list_projects_using_module(
    session: AsyncSession, module_id: UUID
) -> list[ProjectSummaryResponse]:
    svc = _service(session)
    projects = await SqlAlchemyProjectRepository(session).list_for_module(module_id)
    out: list[ProjectSummaryResponse] = []
    for p in projects:
        agg = await svc.compute_aggregates(p.id)
        out.append(await _hydrate_summary_with_customer(session, p, agg=agg))
    return out


# ============================================================================
# Interest links (sub-entity under a project)
# ============================================================================


@router.post(
    "/{project_id}/interest-links",
    response_model=ProjectInterestLinkResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_project_interest_link(
    project_id: UUID,
    payload: ProjectInterestLinkCreateRequest,
    _user: Annotated[User, Depends(require_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ProjectInterestLinkResponse:
    # 404 if project missing.
    await _service(session).get(project_id)
    from app.domain.entities.project_interest_link import ProjectInterestLink

    repo = SqlAlchemyProjectInterestLinkRepository(session)
    saved = await repo.save(
        ProjectInterestLink(
            project_id=project_id,
            name=payload.name,
            url=payload.url,
            sort_order=payload.sort_order,
        )
    )
    return ProjectInterestLinkResponse.model_validate(saved)


@router.patch(
    "/{project_id}/interest-links/{link_id}",
    response_model=ProjectInterestLinkResponse,
)
async def patch_project_interest_link(
    project_id: UUID,
    link_id: UUID,
    payload: ProjectInterestLinkUpdateRequest,
    _user: Annotated[User, Depends(require_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ProjectInterestLinkResponse:
    await _service(session).get(project_id)
    repo = SqlAlchemyProjectInterestLinkRepository(session)
    current = await repo.get(link_id)
    if current is None or current.project_id != project_id:
        from app.core.exceptions import ProjectNotFoundError

        raise ProjectNotFoundError(
            f"project_interest_link not found: {link_id} (in project {project_id})"
        )
    fs = payload.model_fields_set
    if "name" in fs and payload.name is not None:
        current.name = payload.name
    if "url" in fs and payload.url is not None:
        current.url = payload.url
    if "sort_order" in fs and payload.sort_order is not None:
        current.sort_order = payload.sort_order
    updated = await repo.update(current)
    return ProjectInterestLinkResponse.model_validate(updated)


@router.delete(
    "/{project_id}/interest-links/{link_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_project_interest_link(
    project_id: UUID,
    link_id: UUID,
    _user: Annotated[User, Depends(require_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> Response:
    await _service(session).get(project_id)
    repo = SqlAlchemyProjectInterestLinkRepository(session)
    current = await repo.get(link_id)
    if current is not None and current.project_id == project_id:
        await repo.delete(link_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# Silence "unused" lint on the module-repo import (it's intentionally
# transitively referenced via the modules router import patterns).
_ = SqlAlchemyModuleRepository
