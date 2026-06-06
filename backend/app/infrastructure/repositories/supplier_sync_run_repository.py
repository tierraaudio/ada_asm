"""SQLAlchemy repository for `supplier_sync_runs` + `supplier_sync_errors`.

Read-only from the API layer (the Celery task writes; the admin endpoint
reads). The Celery task uses the ORM directly inside `asyncio.run(...)`
to keep its write path self-contained — this repository exists to back
the admin endpoints (`GET /supplier-sync/runs`, etc.).
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.supplier_sync_error import SupplierSyncError
from app.domain.entities.supplier_sync_run import SupplierSyncRun
from app.infrastructure.db.models.supplier_sync_error import SupplierSyncErrorModel
from app.infrastructure.db.models.supplier_sync_run import SupplierSyncRunModel


def _to_run_entity(row: SupplierSyncRunModel) -> SupplierSyncRun:
    return SupplierSyncRun(
        id=row.id,
        supplier=row.supplier,  # type: ignore[arg-type]
        started_at=row.started_at,
        finished_at=row.finished_at,
        components_processed=row.components_processed,
        components_updated=row.components_updated,
        errors_count=row.errors_count,
        status=row.status,  # type: ignore[arg-type]
        error_summary=row.error_summary,
        created_at=row.created_at,
    )


def _to_error_entity(row: SupplierSyncErrorModel) -> SupplierSyncError:
    return SupplierSyncError(
        id=row.id,
        run_id=row.run_id,
        component_id=row.component_id,
        supplier=row.supplier,  # type: ignore[arg-type]
        error_code=row.error_code,  # type: ignore[arg-type]
        error_message=row.error_message,
        occurred_at=row.occurred_at,
    )


class SqlAlchemySupplierSyncRunRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_recent(
        self,
        *,
        limit: int = 50,
        supplier: str | None = None,
    ) -> list[SupplierSyncRun]:
        stmt = select(SupplierSyncRunModel).order_by(
            SupplierSyncRunModel.started_at.desc()
        )
        if supplier is not None:
            stmt = stmt.where(SupplierSyncRunModel.supplier == supplier)
        stmt = stmt.limit(min(max(limit, 1), 200))
        result = await self._session.execute(stmt)
        return [_to_run_entity(row) for row in result.scalars().all()]

    async def get(self, run_id: UUID) -> SupplierSyncRun | None:
        row = await self._session.get(SupplierSyncRunModel, run_id)
        return _to_run_entity(row) if row is not None else None

    async def list_errors_for_run(
        self,
        run_id: UUID,
        *,
        limit: int = 200,
    ) -> list[SupplierSyncError]:
        stmt = (
            select(SupplierSyncErrorModel)
            .where(SupplierSyncErrorModel.run_id == run_id)
            .order_by(SupplierSyncErrorModel.occurred_at.desc())
            .limit(min(max(limit, 1), 1000))
        )
        result = await self._session.execute(stmt)
        return [_to_error_entity(row) for row in result.scalars().all()]
