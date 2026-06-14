"""Admin HTTP routes for inspecting / triggering supplier syncs.

Endpoints:

- `GET  /api/v1/supplier-sync/runs` — paginated list of recent runs.
- `GET  /api/v1/supplier-sync/runs/{id}/errors` — errors for one run.
- `POST /api/v1/supplier-sync/runs?supplier=<code>` — enqueue an ad-hoc
  sync for one supplier. Returns the `run_id` + Celery `task_id`
  immediately (HTTP 202).
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import get_db_session, require_user
from app.api.v1.schemas.supplier_sync import (
    SupplierCodeLiteral,
    SupplierSyncErrorResponse,
    SupplierSyncRunResponse,
    TriggerSyncResponse,
)
from app.core.config import get_settings
from app.core.exceptions import (
    SupplierNotEnabledError,
    SupplierSyncEnqueueFailedError,
    SupplierSyncRunNotFoundError,
)
from app.domain.entities.user import User
from app.infrastructure.repositories.supplier_sync_run_repository import (
    SqlAlchemySupplierSyncRunRepository,
)
from app.infrastructure.suppliers.registry import enabled_adapters

router = APIRouter(prefix="/supplier-sync", tags=["supplier-sync"])

_log = logging.getLogger(__name__)

# Hard ceiling on the broker publish. kombu's connection handling is
# synchronous and retries internally; without a budget a Redis outage
# turns this request into a multi-minute hang.
_ENQUEUE_TIMEOUT_SECONDS = 15.0


@router.get(
    "/runs",
    response_model=list[SupplierSyncRunResponse],
    summary="List recent supplier sync runs",
)
async def list_runs(
    _user: Annotated[User, Depends(require_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    supplier: Annotated[SupplierCodeLiteral | None, Query()] = None,
) -> list[SupplierSyncRunResponse]:
    repo = SqlAlchemySupplierSyncRunRepository(session)
    runs = await repo.list_recent(limit=limit, supplier=supplier)
    return [
        SupplierSyncRunResponse(
            id=r.id,
            supplier=r.supplier,
            started_at=r.started_at,
            finished_at=r.finished_at,
            components_processed=r.components_processed,
            components_updated=r.components_updated,
            errors_count=r.errors_count,
            status=r.status,
            error_summary=r.error_summary,
        )
        for r in runs
    ]


@router.get(
    "/runs/{run_id}/errors",
    response_model=list[SupplierSyncErrorResponse],
    summary="List per-component errors for one sync run",
)
async def list_errors_for_run(
    _user: Annotated[User, Depends(require_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    run_id: UUID,
    limit: Annotated[int, Query(ge=1, le=1000)] = 200,
) -> list[SupplierSyncErrorResponse]:
    repo = SqlAlchemySupplierSyncRunRepository(session)
    run = await repo.get(run_id)
    if run is None:
        raise SupplierSyncRunNotFoundError(f"Run {run_id} not found")
    errors = await repo.list_errors_for_run(run_id, limit=limit)
    return [
        SupplierSyncErrorResponse(
            id=e.id,
            run_id=e.run_id,
            component_id=e.component_id,
            supplier=e.supplier,
            error_code=e.error_code,
            error_message=e.error_message,
            occurred_at=e.occurred_at,
        )
        for e in errors
    ]


@router.post(
    "/runs",
    response_model=TriggerSyncResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Enqueue an ad-hoc sync for one supplier",
)
async def trigger_supplier_sync(
    _user: Annotated[User, Depends(require_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    response: Response,
    supplier: Annotated[SupplierCodeLiteral, Query(...)],
) -> TriggerSyncResponse:
    # Validate the supplier is BOTH listed in the flag AND has credentials
    # — same gate the registry applies. The check here gives the operator
    # a fast 422 instead of a silent no-op task.
    settings = get_settings()
    if supplier not in settings.supplier_sync_enabled_suppliers:
        raise SupplierNotEnabledError(
            f"Supplier {supplier!r} is not in SUPPLIER_SYNC_ENABLED_SUPPLIERS"
        )
    if supplier not in {a.code for a in enabled_adapters(settings=settings)}:
        raise SupplierNotEnabledError(
            f"Supplier {supplier!r} is enabled but credentials are missing"
        )

    # Pre-create the `supplier_sync_runs` row HERE so the response can
    # return the real run_id. The Celery task will pick it up by id.
    from app.infrastructure.db.models.supplier_sync_run import (
        SupplierSyncRunModel,
    )
    from app.infrastructure.tasks.supplier_sync import sync_one_supplier

    run_id = uuid4()
    session.add(SupplierSyncRunModel(id=run_id, supplier=supplier, status="running"))
    await session.flush()
    await session.commit()

    # Publish OFF the event loop: kombu's broker I/O is synchronous, so a
    # Redis hiccup inside `.delay()` would otherwise freeze EVERY in-flight
    # request (login included) until kombu's internal retries give up.
    def _enqueue() -> str:
        async_result = sync_one_supplier.apply_async(
            args=(supplier, str(run_id)),
            retry=True,
            retry_policy={
                "max_retries": 2,
                "interval_start": 0,
                "interval_step": 0.5,
                "interval_max": 1,
            },
        )
        return str(async_result.id)

    enqueue_started = time.monotonic()
    try:
        task_id = await asyncio.wait_for(
            asyncio.to_thread(_enqueue), timeout=_ENQUEUE_TIMEOUT_SECONDS
        )
    except Exception as exc:
        _log.error(
            "supplier_sync.enqueue.failed supplier=%s run_id=%s duration_ms=%d err=%s.%s msg=%s",
            supplier,
            run_id,
            (time.monotonic() - enqueue_started) * 1000,
            type(exc).__module__,
            type(exc).__name__,
            exc,
        )
        # Close the orphaned run row so it doesn't sit in `running` forever.
        run_row = await session.get(SupplierSyncRunModel, run_id)
        if run_row is not None:
            run_row.status = "failed"
            run_row.error_summary = "ENQUEUE_FAILED: broker unreachable"
            run_row.finished_at = datetime.now(UTC)
            await session.commit()
        raise SupplierSyncEnqueueFailedError(
            f"Could not enqueue sync for {supplier!r}: broker unreachable"
        ) from exc

    _log.info(
        "supplier_sync.enqueue.done supplier=%s run_id=%s task_id=%s duration_ms=%d",
        supplier,
        run_id,
        task_id,
        (time.monotonic() - enqueue_started) * 1000,
    )
    response.headers["X-Task-Id"] = task_id
    return TriggerSyncResponse(run_id=run_id, task_id=task_id)
