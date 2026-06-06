"""Integration tests for the projects surface.

Covers the full `/api/v1/projects` surface (list / create / get / patch /
delete / children CRUD / price-history / stock-events / interest-links) plus
the `projects-using` endpoints exposed from the components + modules routers.

Mirrors the style of `test_modules.py` — a single file with a shared
`_create_project` helper and a small catalogue fixture so we don't repeat
the boilerplate per endpoint.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.domain.entities.component import Component

pytestmark = pytest.mark.integration


async def _create_project(
    api_client: AsyncClient, headers: dict[str, str], **overrides: object
) -> dict:
    body = {
        "code": "PRJ-TEST-001",
        "name": "Test project",
        **overrides,
    }
    response = await api_client.post("/api/v1/projects", headers=headers, json=body)
    assert response.status_code == 201, response.text
    return response.json()


async def _create_module(
    api_client: AsyncClient, headers: dict[str, str], **overrides: object
) -> dict:
    body = {
        "sku": "MOD-PRJ-001",
        "name": "Module for project tests",
        **overrides,
    }
    response = await api_client.post("/api/v1/modules", headers=headers, json=body)
    assert response.status_code == 201, response.text
    return response.json()


async def _create_customer(
    api_client: AsyncClient, headers: dict[str, str], **overrides: object
) -> dict:
    body = {"holded_id": "HOLD-PRJ-001", "name": "Customer for project tests", **overrides}
    response = await api_client.post("/api/v1/customers", headers=headers, json=body)
    assert response.status_code == 201, response.text
    return response.json()


# ---------- list / create ----------


async def test_list_empty(api_client: AsyncClient, auth_headers: dict[str, str]) -> None:
    response = await api_client.get("/api/v1/projects", headers=auth_headers)
    assert response.status_code == 200
    assert response.json() == {"items": [], "total": 0, "page": 1, "page_size": 25}


async def test_list_requires_auth(api_client: AsyncClient) -> None:
    response = await api_client.get("/api/v1/projects")
    assert response.status_code == 401


async def test_create_requires_auth(api_client: AsyncClient) -> None:
    response = await api_client.post(
        "/api/v1/projects", json={"code": "PRJ-NOAUTH", "name": "Nope"}
    )
    assert response.status_code == 401


async def test_create_then_list(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    await _create_project(api_client, auth_headers, code="PRJ-A", name="Alpha")
    await _create_project(api_client, auth_headers, code="PRJ-B", name="Beta")
    response = await api_client.get("/api/v1/projects", headers=auth_headers)
    body = response.json()
    assert body["total"] == 2
    codes = {item["code"] for item in body["items"]}
    assert codes == {"PRJ-A", "PRJ-B"}


async def test_create_with_full_payload_hydrates_customer(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    customer = await _create_customer(api_client, auth_headers)
    response = await api_client.post(
        "/api/v1/projects",
        headers=auth_headers,
        json={
            "code": "PRJ-FULL",
            "name": "Full project",
            "description": "with all the fields",
            "status": "En proceso",
            "customer_id": customer["id"],
            "icon": "🚀",
            "color": "#ff0000",
            "tags": ["alpha", "beta"],
            "version": "v1.2",
            "fecha_inicio": "2026-01-01",
            "fecha_entrega_estimada": "2026-06-01",
            "notas": "test notes",
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["code"] == "PRJ-FULL"
    assert body["status"] == "En proceso"
    assert body["customer"]["id"] == customer["id"]
    assert body["icon"] == "🚀"
    assert body["color"] == "#ff0000"
    assert body["tags"] == ["alpha", "beta"]
    assert body["version"] == "v1.2"
    assert body["fecha_inicio"] == "2026-01-01"
    assert body["fecha_entrega_estimada"] == "2026-06-01"


async def test_create_completado_auto_fills_fecha_entrega_real(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    response = await api_client.post(
        "/api/v1/projects",
        headers=auth_headers,
        json={"code": "PRJ-DONE", "name": "Delivered", "status": "Completado"},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "Completado"
    assert body["fecha_entrega_real"] is not None


async def test_create_dup_code_returns_409(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    await _create_project(api_client, auth_headers, code="PRJ-DUP")
    response = await api_client.post(
        "/api/v1/projects",
        headers=auth_headers,
        json={"code": "prj-dup", "name": "Same code, different case"},
    )
    assert response.status_code == 409
    assert response.json()["code"] == "PROJECT_CODE_ALREADY_REGISTERED"


async def test_create_validation_error(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    response = await api_client.post(
        "/api/v1/projects",
        headers=auth_headers,
        json={"code": "", "name": "missing code"},
    )
    assert response.status_code == 422


# ---------- list filters ----------


async def test_list_search_q_by_code_or_name(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    await _create_project(api_client, auth_headers, code="PRJ-SAT", name="Satellite Bus")
    await _create_project(api_client, auth_headers, code="PRJ-RVR", name="Rover")
    response = await api_client.get(
        "/api/v1/projects?q=satellite", headers=auth_headers
    )
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["code"] == "PRJ-SAT"


async def test_list_filter_by_status(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    await _create_project(api_client, auth_headers, code="PRJ-PEND", name="Pending")
    await _create_project(
        api_client,
        auth_headers,
        code="PRJ-PROC",
        name="In progress",
        status="En proceso",
    )
    response = await api_client.get(
        "/api/v1/projects?status=En%20proceso", headers=auth_headers
    )
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["code"] == "PRJ-PROC"


async def test_list_filter_by_customer_id(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    customer = await _create_customer(api_client, auth_headers)
    await _create_project(
        api_client,
        auth_headers,
        code="PRJ-CUS",
        name="With customer",
        customer_id=customer["id"],
    )
    await _create_project(
        api_client, auth_headers, code="PRJ-NOCUS", name="No customer"
    )
    response = await api_client.get(
        f"/api/v1/projects?customer_id={customer['id']}", headers=auth_headers
    )
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["code"] == "PRJ-CUS"


async def test_list_pagination(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    for i in range(3):
        await _create_project(
            api_client, auth_headers, code=f"PRJ-PAG-{i}", name=f"Project {i}"
        )
    response = await api_client.get(
        "/api/v1/projects?page=1&page_size=2", headers=auth_headers
    )
    body = response.json()
    assert body["total"] == 3
    assert body["page"] == 1
    assert body["page_size"] == 2
    assert len(body["items"]) == 2


# ---------- get / patch / delete ----------


async def test_get_404(api_client: AsyncClient, auth_headers: dict[str, str]) -> None:
    response = await api_client.get(
        "/api/v1/projects/00000000-0000-0000-0000-000000000000",
        headers=auth_headers,
    )
    assert response.status_code == 404
    assert response.json()["code"] == "PROJECT_NOT_FOUND"


async def test_get_detail_empty_children(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    created = await _create_project(api_client, auth_headers)
    response = await api_client.get(
        f"/api/v1/projects/{created['id']}", headers=auth_headers
    )
    assert response.status_code == 200
    body = response.json()
    assert body["children"] == []
    assert body["interest_links"] == []
    assert body["buildable_stock"] == 0


async def test_patch_updates_fields(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    created = await _create_project(api_client, auth_headers)
    response = await api_client.patch(
        f"/api/v1/projects/{created['id']}",
        headers=auth_headers,
        json={"name": "Renamed", "notas": "now with note", "tags": ["new"]},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Renamed"
    assert body["notas"] == "now with note"
    assert body["tags"] == ["new"]


async def test_patch_transition_to_completado_auto_fills_date(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    created = await _create_project(api_client, auth_headers)
    assert created["fecha_entrega_real"] is None
    response = await api_client.patch(
        f"/api/v1/projects/{created['id']}",
        headers=auth_headers,
        json={"status": "Completado"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "Completado"
    assert body["fecha_entrega_real"] is not None


async def test_patch_transition_to_completado_respects_explicit_date(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    created = await _create_project(api_client, auth_headers)
    response = await api_client.patch(
        f"/api/v1/projects/{created['id']}",
        headers=auth_headers,
        json={"status": "Completado", "fecha_entrega_real": "2026-05-05"},
    )
    assert response.status_code == 200
    assert response.json()["fecha_entrega_real"] == "2026-05-05"


async def test_patch_all_optional_fields(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    created = await _create_project(api_client, auth_headers)
    response = await api_client.patch(
        f"/api/v1/projects/{created['id']}",
        headers=auth_headers,
        json={
            "code": "PRJ-RENAMED",
            "name": "Renamed",
            "description": "desc",
            "status": "En proceso",
            "icon": "🤖",
            "color": "#00ff00",
            "tags": ["x", "y"],
            "version": "v2",
            "fecha_inicio": "2026-02-02",
            "fecha_entrega_estimada": "2026-09-09",
            "notas": "n",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["code"] == "PRJ-RENAMED"
    assert body["icon"] == "🤖"
    assert body["color"] == "#00ff00"
    assert body["version"] == "v2"


async def test_patch_404_unknown(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    response = await api_client.patch(
        "/api/v1/projects/00000000-0000-0000-0000-000000000000",
        headers=auth_headers,
        json={"name": "Ghost"},
    )
    assert response.status_code == 404


async def test_delete_archives_project(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    created = await _create_project(api_client, auth_headers)
    response = await api_client.delete(
        f"/api/v1/projects/{created['id']}", headers=auth_headers
    )
    assert response.status_code == 204
    # Soft-deleted projects are excluded from the default list...
    listed = await api_client.get("/api/v1/projects", headers=auth_headers)
    assert listed.json()["total"] == 0
    # ...but reappear when include_archived=true.
    listed = await api_client.get(
        "/api/v1/projects?include_archived=true", headers=auth_headers
    )
    body = listed.json()
    assert body["total"] == 1
    assert body["items"][0]["status"] == "Archivado"


async def test_delete_unknown_returns_404(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    response = await api_client.delete(
        "/api/v1/projects/00000000-0000-0000-0000-000000000000",
        headers=auth_headers,
    )
    assert response.status_code == 404


# ---------- children: add / update / remove ----------


async def test_add_child_module(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    project = await _create_project(api_client, auth_headers)
    module = await _create_module(api_client, auth_headers)
    response = await api_client.post(
        f"/api/v1/projects/{project['id']}/children",
        headers=auth_headers,
        json={"child_module_id": module["id"], "quantity": 2},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["child_module_id"] == module["id"]
    assert body["quantity"] == 2
    assert body["child_module"]["sku"] == module["sku"]


async def test_add_child_component(
    api_client: AsyncClient,
    auth_headers: dict[str, str],
    seeded_components_catalogue: list[Component],
) -> None:
    project = await _create_project(api_client, auth_headers)
    component = seeded_components_catalogue[0]
    response = await api_client.post(
        f"/api/v1/projects/{project['id']}/children",
        headers=auth_headers,
        json={"child_component_id": str(component.id), "quantity": 5, "notes": "spare"},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["child_component_id"] == str(component.id)
    assert body["quantity"] == 5
    assert body["notes"] == "spare"
    assert body["child_component"]["mpn"] == component.mpn


async def test_add_child_xor_violation_both_set(
    api_client: AsyncClient,
    auth_headers: dict[str, str],
    seeded_components_catalogue: list[Component],
) -> None:
    project = await _create_project(api_client, auth_headers)
    module = await _create_module(api_client, auth_headers)
    component = seeded_components_catalogue[0]
    response = await api_client.post(
        f"/api/v1/projects/{project['id']}/children",
        headers=auth_headers,
        json={
            "child_module_id": module["id"],
            "child_component_id": str(component.id),
            "quantity": 1,
        },
    )
    assert response.status_code == 422


async def test_add_child_xor_violation_neither_set(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    project = await _create_project(api_client, auth_headers)
    response = await api_client.post(
        f"/api/v1/projects/{project['id']}/children",
        headers=auth_headers,
        json={"quantity": 1},
    )
    assert response.status_code == 422


async def test_add_child_invalid_module_id_returns_422(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    project = await _create_project(api_client, auth_headers)
    response = await api_client.post(
        f"/api/v1/projects/{project['id']}/children",
        headers=auth_headers,
        json={
            "child_module_id": "00000000-0000-0000-0000-000000000000",
            "quantity": 1,
        },
    )
    assert response.status_code == 422
    assert response.json()["code"] == "INVALID_CHILD_REFERENCE"


async def test_add_child_invalid_component_id_returns_422(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    project = await _create_project(api_client, auth_headers)
    response = await api_client.post(
        f"/api/v1/projects/{project['id']}/children",
        headers=auth_headers,
        json={
            "child_component_id": "00000000-0000-0000-0000-000000000000",
            "quantity": 1,
        },
    )
    assert response.status_code == 422
    assert response.json()["code"] == "INVALID_CHILD_REFERENCE"


async def test_add_child_duplicate_returns_409(
    api_client: AsyncClient,
    auth_headers: dict[str, str],
    seeded_components_catalogue: list[Component],
) -> None:
    project = await _create_project(api_client, auth_headers)
    component = seeded_components_catalogue[0]
    body = {"child_component_id": str(component.id), "quantity": 1}
    first = await api_client.post(
        f"/api/v1/projects/{project['id']}/children", headers=auth_headers, json=body
    )
    assert first.status_code == 201
    second = await api_client.post(
        f"/api/v1/projects/{project['id']}/children", headers=auth_headers, json=body
    )
    assert second.status_code == 422
    assert second.json()["code"] == "CHILD_ALREADY_PRESENT"


async def test_add_child_unknown_project_returns_404(
    api_client: AsyncClient,
    auth_headers: dict[str, str],
    seeded_components_catalogue: list[Component],
) -> None:
    component = seeded_components_catalogue[0]
    response = await api_client.post(
        "/api/v1/projects/00000000-0000-0000-0000-000000000000/children",
        headers=auth_headers,
        json={"child_component_id": str(component.id), "quantity": 1},
    )
    assert response.status_code == 404


async def test_patch_child_updates_quantity_notes_sort_order(
    api_client: AsyncClient,
    auth_headers: dict[str, str],
    seeded_components_catalogue: list[Component],
) -> None:
    project = await _create_project(api_client, auth_headers)
    component = seeded_components_catalogue[0]
    add = await api_client.post(
        f"/api/v1/projects/{project['id']}/children",
        headers=auth_headers,
        json={"child_component_id": str(component.id), "quantity": 1},
    )
    edge = add.json()
    response = await api_client.patch(
        f"/api/v1/projects/{project['id']}/children/{edge['id']}",
        headers=auth_headers,
        json={"quantity": 7, "notes": "updated", "sort_order": 3},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["quantity"] == 7
    assert body["notes"] == "updated"
    assert body["sort_order"] == 3


async def test_patch_child_quantity_invalid_returns_422(
    api_client: AsyncClient,
    auth_headers: dict[str, str],
    seeded_components_catalogue: list[Component],
) -> None:
    project = await _create_project(api_client, auth_headers)
    component = seeded_components_catalogue[0]
    add = await api_client.post(
        f"/api/v1/projects/{project['id']}/children",
        headers=auth_headers,
        json={"child_component_id": str(component.id), "quantity": 1},
    )
    edge = add.json()
    response = await api_client.patch(
        f"/api/v1/projects/{project['id']}/children/{edge['id']}",
        headers=auth_headers,
        json={"quantity": 0},
    )
    assert response.status_code == 422


async def test_patch_child_unknown_returns_404(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    project = await _create_project(api_client, auth_headers)
    response = await api_client.patch(
        f"/api/v1/projects/{project['id']}/children/00000000-0000-0000-0000-000000000000",
        headers=auth_headers,
        json={"quantity": 2},
    )
    assert response.status_code == 404


async def test_remove_child_idempotent(
    api_client: AsyncClient,
    auth_headers: dict[str, str],
    seeded_components_catalogue: list[Component],
) -> None:
    project = await _create_project(api_client, auth_headers)
    component = seeded_components_catalogue[0]
    add = await api_client.post(
        f"/api/v1/projects/{project['id']}/children",
        headers=auth_headers,
        json={"child_component_id": str(component.id), "quantity": 1},
    )
    edge_id = add.json()["id"]
    response = await api_client.delete(
        f"/api/v1/projects/{project['id']}/children/{edge_id}", headers=auth_headers
    )
    assert response.status_code == 204
    # Idempotent — deleting again still returns 204.
    response = await api_client.delete(
        f"/api/v1/projects/{project['id']}/children/{edge_id}", headers=auth_headers
    )
    assert response.status_code == 204


# ---------- aggregates ----------


async def test_get_detail_aggregates_via_module_child(
    api_client: AsyncClient,
    auth_headers: dict[str, str],
    seeded_components_catalogue: list[Component],
) -> None:
    """Exercises the descendant walk through a module + buildable_stock
    against a module edge's `module.stock`.
    """
    module = await _create_module(api_client, auth_headers, sku="MOD-BUILD", stock=4)
    component = next(
        c for c in seeded_components_catalogue if c.mpn == "STM32F407VGT6"
    )
    # Module contains the component.
    await api_client.post(
        f"/api/v1/modules/{module['id']}/children",
        headers=auth_headers,
        json={"child_component_id": str(component.id), "quantity": 1},
    )
    project = await _create_project(api_client, auth_headers)
    # Project's only child is the module (quantity=2 — 4 // 2 = 2 buildable).
    await api_client.post(
        f"/api/v1/projects/{project['id']}/children",
        headers=auth_headers,
        json={"child_module_id": module["id"], "quantity": 2},
    )
    response = await api_client.get(
        f"/api/v1/projects/{project['id']}", headers=auth_headers
    )
    body = response.json()
    assert body["aggregated_tier"] == component.tier
    assert body["aggregated_nato_score"] == component.nato_score
    assert body["buildable_stock"] == 2


async def test_get_detail_hydrates_aggregates(
    api_client: AsyncClient,
    auth_headers: dict[str, str],
    seeded_components_catalogue: list[Component],
) -> None:
    project = await _create_project(api_client, auth_headers)
    # Pick the worst NATO score (D) + worst tier (1) from the catalogue.
    esp = next(c for c in seeded_components_catalogue if c.mpn == "ESP32-WROOM-32")
    stm = next(c for c in seeded_components_catalogue if c.mpn == "STM32F407VGT6")
    await api_client.post(
        f"/api/v1/projects/{project['id']}/children",
        headers=auth_headers,
        json={"child_component_id": str(esp.id), "quantity": 1},
    )
    await api_client.post(
        f"/api/v1/projects/{project['id']}/children",
        headers=auth_headers,
        json={"child_component_id": str(stm.id), "quantity": 1},
    )

    response = await api_client.get(
        f"/api/v1/projects/{project['id']}", headers=auth_headers
    )
    body = response.json()
    assert body["aggregated_nato_score"] == "D"
    assert body["aggregated_tier"] == 1
    assert len(body["children"]) == 2
    # Both ESP and STM have stock — buildable_stock = min(stock_esp, stock_stm).
    assert body["buildable_stock"] >= 0


# ---------- price history ----------


async def test_price_history_empty_when_no_descendants(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    project = await _create_project(api_client, auth_headers)
    response = await api_client.get(
        f"/api/v1/projects/{project['id']}/price-history", headers=auth_headers
    )
    assert response.status_code == 200
    assert response.json()["series"] == []
    assert response.json()["period"] == "year"


async def test_price_history_with_explicit_period(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    project = await _create_project(api_client, auth_headers)
    response = await api_client.get(
        f"/api/v1/projects/{project['id']}/price-history?period=week",
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["period"] == "week"


async def test_price_history_unknown_project_returns_404(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    response = await api_client.get(
        "/api/v1/projects/00000000-0000-0000-0000-000000000000/price-history",
        headers=auth_headers,
    )
    assert response.status_code == 404


# ---------- stock events ----------


async def test_stock_events_empty(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    project = await _create_project(api_client, auth_headers)
    response = await api_client.get(
        f"/api/v1/projects/{project['id']}/stock-events", headers=auth_headers
    )
    assert response.status_code == 200
    body = response.json()
    assert body["items"] == []
    assert body["total"] == 0


async def test_stock_events_unknown_project_returns_404(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    response = await api_client.get(
        "/api/v1/projects/00000000-0000-0000-0000-000000000000/stock-events",
        headers=auth_headers,
    )
    assert response.status_code == 404


# ---------- cross-feature: projects-using ----------


async def test_projects_using_component_returns_referencing_projects(
    api_client: AsyncClient,
    auth_headers: dict[str, str],
    seeded_components_catalogue: list[Component],
) -> None:
    component = seeded_components_catalogue[0]
    project = await _create_project(api_client, auth_headers)
    await api_client.post(
        f"/api/v1/projects/{project['id']}/children",
        headers=auth_headers,
        json={"child_component_id": str(component.id), "quantity": 1},
    )
    response = await api_client.get(
        f"/api/v1/components/{component.id}/projects-using", headers=auth_headers
    )
    assert response.status_code == 200
    rows = response.json()
    assert len(rows) == 1
    assert rows[0]["id"] == project["id"]


async def test_projects_using_component_empty_when_unreferenced(
    api_client: AsyncClient,
    auth_headers: dict[str, str],
    seeded_components_catalogue: list[Component],
) -> None:
    component = seeded_components_catalogue[0]
    response = await api_client.get(
        f"/api/v1/components/{component.id}/projects-using", headers=auth_headers
    )
    assert response.status_code == 200
    assert response.json() == []


async def test_projects_using_module_returns_referencing_projects(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    module = await _create_module(api_client, auth_headers)
    project = await _create_project(api_client, auth_headers)
    await api_client.post(
        f"/api/v1/projects/{project['id']}/children",
        headers=auth_headers,
        json={"child_module_id": module["id"], "quantity": 1},
    )
    response = await api_client.get(
        f"/api/v1/modules/{module['id']}/projects-using", headers=auth_headers
    )
    assert response.status_code == 200
    rows = response.json()
    assert len(rows) == 1
    assert rows[0]["id"] == project["id"]


async def test_projects_using_module_empty_when_unreferenced(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    module = await _create_module(api_client, auth_headers)
    response = await api_client.get(
        f"/api/v1/modules/{module['id']}/projects-using", headers=auth_headers
    )
    assert response.status_code == 200
    assert response.json() == []


# ---------- interest links ----------


async def test_create_and_list_interest_link(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    project = await _create_project(api_client, auth_headers)
    create = await api_client.post(
        f"/api/v1/projects/{project['id']}/interest-links",
        headers=auth_headers,
        json={"name": "Spec sheet", "url": "https://example.com/spec", "sort_order": 1},
    )
    assert create.status_code == 201, create.text
    link = create.json()
    assert link["name"] == "Spec sheet"

    # Visible on the project detail.
    detail = await api_client.get(
        f"/api/v1/projects/{project['id']}", headers=auth_headers
    )
    assert detail.status_code == 200
    links = detail.json()["interest_links"]
    assert len(links) == 1
    assert links[0]["id"] == link["id"]


async def test_create_interest_link_unknown_project_returns_404(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    response = await api_client.post(
        "/api/v1/projects/00000000-0000-0000-0000-000000000000/interest-links",
        headers=auth_headers,
        json={"name": "x", "url": "https://x"},
    )
    assert response.status_code == 404


async def test_patch_interest_link_updates_fields(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    project = await _create_project(api_client, auth_headers)
    create = await api_client.post(
        f"/api/v1/projects/{project['id']}/interest-links",
        headers=auth_headers,
        json={"name": "Original", "url": "https://x", "sort_order": 0},
    )
    link_id = create.json()["id"]
    response = await api_client.patch(
        f"/api/v1/projects/{project['id']}/interest-links/{link_id}",
        headers=auth_headers,
        json={"name": "Renamed", "url": "https://y", "sort_order": 9},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Renamed"
    assert body["url"] == "https://y"
    assert body["sort_order"] == 9


async def test_patch_interest_link_unknown_returns_404(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    project = await _create_project(api_client, auth_headers)
    response = await api_client.patch(
        f"/api/v1/projects/{project['id']}/interest-links/00000000-0000-0000-0000-000000000000",
        headers=auth_headers,
        json={"name": "Ghost"},
    )
    assert response.status_code == 404


async def test_delete_interest_link(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    project = await _create_project(api_client, auth_headers)
    create = await api_client.post(
        f"/api/v1/projects/{project['id']}/interest-links",
        headers=auth_headers,
        json={"name": "Spec", "url": "https://x"},
    )
    link_id = create.json()["id"]
    response = await api_client.delete(
        f"/api/v1/projects/{project['id']}/interest-links/{link_id}",
        headers=auth_headers,
    )
    assert response.status_code == 204
    # Idempotent — deleting an unknown link in the same project still returns 204.
    response = await api_client.delete(
        f"/api/v1/projects/{project['id']}/interest-links/{link_id}",
        headers=auth_headers,
    )
    assert response.status_code == 204


async def test_delete_interest_link_unknown_project_returns_404(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    response = await api_client.delete(
        "/api/v1/projects/00000000-0000-0000-0000-000000000000/interest-links/00000000-0000-0000-0000-000000000000",
        headers=auth_headers,
    )
    assert response.status_code == 404
