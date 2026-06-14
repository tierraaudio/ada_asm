"""Integration tests for the `/api/v1/supplier-sync/*` admin endpoints."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from httpx import AsyncClient

from app.infrastructure.db.models.supplier_sync_error import SupplierSyncErrorModel
from app.infrastructure.db.models.supplier_sync_run import SupplierSyncRunModel
from app.infrastructure.db.session import get_session_factory

pytestmark = pytest.mark.asyncio


async def _seed_run(
    *,
    supplier: str = "mouser",
    status: str = "success",
    errors: int = 0,
    processed: int = 1,
    updated: int = 1,
) -> tuple[str, str | None]:
    """Insert a `supplier_sync_runs` row directly and optionally one error
    row pointing at it. Returns (run_id, error_id_or_none)."""

    factory = get_session_factory()
    async with factory() as session:
        run_id = uuid4()
        session.add(
            SupplierSyncRunModel(
                id=run_id,
                supplier=supplier,
                status=status,
                components_processed=processed,
                components_updated=updated,
                errors_count=errors,
                finished_at=datetime.now(UTC),
            )
        )
        await session.flush()
        error_id = None
        if errors > 0:
            # Need a component_id to satisfy FK — seed a dummy component.
            from app.domain.entities.component import Component
            from app.infrastructure.repositories.component_repository import (
                SqlAlchemyComponentRepository,
            )

            repo = SqlAlchemyComponentRepository(session)
            comp = await repo.save(
                Component(
                    mpn=f"TEST-ERR-{uuid4().hex[:6].upper()}",
                    name="Errored Component",
                    family="Sensores",
                    stock=0,
                    tier=3,
                    nato_score="B",
                )
            )
            error_id = uuid4()
            session.add(
                SupplierSyncErrorModel(
                    id=error_id,
                    run_id=run_id,
                    component_id=comp.id,
                    supplier=supplier,
                    error_code="HTTP_5XX",
                    error_message="boom",
                )
            )
        await session.commit()
        return str(run_id), (str(error_id) if error_id else None)


async def test_list_runs_returns_recent_in_reverse_chronological(
    api_client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    a, _ = await _seed_run(supplier="mouser", status="success")
    b, _ = await _seed_run(supplier="digikey", status="partial", errors=1)

    response = await api_client.get(
        "/api/v1/supplier-sync/runs?limit=10",
        headers=auth_headers,
    )
    assert response.status_code == 200
    body = response.json()
    ids = [r["id"] for r in body]
    # Most recent (b) comes first.
    assert ids[0] == b
    assert a in ids


async def test_list_runs_filters_by_supplier(
    api_client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    await _seed_run(supplier="mouser", status="success")
    await _seed_run(supplier="digikey", status="success")

    response = await api_client.get(
        "/api/v1/supplier-sync/runs?supplier=digikey",
        headers=auth_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert all(r["supplier"] == "digikey" for r in body)
    assert len(body) >= 1


async def test_list_errors_for_known_run_returns_rows(
    api_client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    run_id, error_id = await _seed_run(
        supplier="mouser",
        status="partial",
        errors=1,
    )
    assert error_id is not None

    response = await api_client.get(
        f"/api/v1/supplier-sync/runs/{run_id}/errors",
        headers=auth_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["id"] == error_id
    assert body[0]["error_code"] == "HTTP_5XX"


async def test_list_errors_for_unknown_run_returns_404(
    api_client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    response = await api_client.get(
        f"/api/v1/supplier-sync/runs/{uuid4()}/errors",
        headers=auth_headers,
    )
    assert response.status_code == 404
    body = response.json()
    assert body["code"] == "SUPPLIER_SYNC_RUN_NOT_FOUND"


async def test_trigger_disabled_supplier_returns_422(
    api_client: AsyncClient,
    auth_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Force RS out of the enabled list so the gate triggers.
    monkeypatch.setenv("SUPPLIER_SYNC_ENABLED_SUPPLIERS", "mouser")
    # Settings is a function call (not a module-level singleton) so the
    # next call to get_settings() picks the new env up. We don't need to
    # reset anything.

    response = await api_client.post(
        "/api/v1/supplier-sync/runs?supplier=rs",
        headers=auth_headers,
    )
    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "SUPPLIER_NOT_ENABLED"


async def test_unauthenticated_request_returns_401(
    api_client: AsyncClient,
) -> None:
    response = await api_client.get("/api/v1/supplier-sync/runs")
    assert response.status_code == 401


async def test_trigger_returns_503_when_enqueue_fails(
    api_client: AsyncClient,
    auth_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If the Celery broker is unreachable the trigger endpoint must fail
    fast with a typed 503 instead of blocking the event loop on kombu's
    internal retry loop."""

    monkeypatch.setenv("SUPPLIER_SYNC_ENABLED_SUPPLIERS", "mouser")
    monkeypatch.setenv("MOUSER_API_KEY", "test-key")

    from app.infrastructure.tasks import supplier_sync as sync_tasks

    def _broken_apply_async(*args: object, **kwargs: object) -> object:
        raise ConnectionError("broker unreachable")

    monkeypatch.setattr(sync_tasks.sync_one_supplier, "apply_async", _broken_apply_async)

    response = await api_client.post(
        "/api/v1/supplier-sync/runs?supplier=mouser",
        headers=auth_headers,
    )
    assert response.status_code == 503
    body = response.json()
    assert body["code"] == "SUPPLIER_SYNC_ENQUEUE_FAILED"
