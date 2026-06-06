"""Integration tests for the modules surface.

Covers every endpoint's happy path + the critical error paths
(404, 409 sku dup, 422 XOR, 422 cycle, 422 duplicate edge), aggregates
hydration, and CASCADE on delete.

Kept in a single file (rather than one-per-endpoint like components) because
the module surface is uniform and a shared catalogue fixture saves a lot
of setup duplication.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.domain.entities.component import Component

pytestmark = pytest.mark.integration


async def _create_module(
    api_client: AsyncClient, headers: dict[str, str], **overrides: object
) -> dict:
    body = {
        "sku": "MOD-TEST-001",
        "name": "Test module",
        "version": "v1.0",
        "stock": 0,
        **overrides,
    }
    response = await api_client.post("/api/v1/modules", headers=headers, json=body)
    assert response.status_code == 201, response.text
    return response.json()


# ---------- list / create ----------


async def test_list_empty(api_client: AsyncClient, auth_headers: dict[str, str]) -> None:
    response = await api_client.get("/api/v1/modules", headers=auth_headers)
    assert response.status_code == 200
    assert response.json() == {"items": [], "total": 0, "page": 1, "page_size": 25}


async def test_list_requires_auth(api_client: AsyncClient) -> None:
    response = await api_client.get("/api/v1/modules")
    assert response.status_code == 401


async def test_create_then_list(api_client: AsyncClient, auth_headers: dict[str, str]) -> None:
    await _create_module(api_client, auth_headers, sku="MOD-A", name="Alpha")
    await _create_module(api_client, auth_headers, sku="MOD-B", name="Beta")
    response = await api_client.get("/api/v1/modules", headers=auth_headers)
    body = response.json()
    assert body["total"] == 2
    skus = {item["sku"] for item in body["items"]}
    assert skus == {"MOD-A", "MOD-B"}


async def test_create_dup_sku_returns_409(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    await _create_module(api_client, auth_headers, sku="MOD-DUP")
    response = await api_client.post(
        "/api/v1/modules",
        headers=auth_headers,
        json={"sku": "mod-dup", "name": "Same sku, different case"},  # case-insensitive
    )
    assert response.status_code == 409
    assert response.json()["code"] == "MODULE_SKU_ALREADY_REGISTERED"


async def test_create_validation_errors(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    response = await api_client.post(
        "/api/v1/modules",
        headers=auth_headers,
        json={"sku": "", "name": "missing sku"},
    )
    assert response.status_code == 422


async def test_list_search_q(api_client: AsyncClient, auth_headers: dict[str, str]) -> None:
    await _create_module(api_client, auth_headers, sku="MOD-PWR-001", name="Power System")
    await _create_module(api_client, auth_headers, sku="MOD-SENS-001", name="Sensor Hub")
    response = await api_client.get("/api/v1/modules?q=power", headers=auth_headers)
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["sku"] == "MOD-PWR-001"


# ---------- get / patch / delete ----------


async def test_get_404(api_client: AsyncClient, auth_headers: dict[str, str]) -> None:
    response = await api_client.get(
        "/api/v1/modules/00000000-0000-0000-0000-000000000000",
        headers=auth_headers,
    )
    assert response.status_code == 404


async def test_patch_updates_fields(api_client: AsyncClient, auth_headers: dict[str, str]) -> None:
    created = await _create_module(api_client, auth_headers)
    response = await api_client.patch(
        f"/api/v1/modules/{created['id']}",
        headers=auth_headers,
        json={"name": "Renamed", "stock": 42},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Renamed"
    assert body["stock"] == 42


async def test_patch_updates_all_optional_fields(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    created = await _create_module(api_client, auth_headers)
    response = await api_client.patch(
        f"/api/v1/modules/{created['id']}",
        headers=auth_headers,
        json={
            "sku": "MOD-RENAMED",
            "name": "Renamed",
            "description": "now with description",
            "version": "v2.0",
            "fabricante": "ACME",
            "location": "G-B-99",
            "tipo_almacenamiento": "Almacén",
            "stock": 7,
            "notas": "a note",
            "fecha_creacion": "2026-01-15",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["sku"] == "MOD-RENAMED"
    assert body["fabricante"] == "ACME"
    assert body["version"] == "v2.0"
    assert body["fecha_creacion"] == "2026-01-15"


async def test_patch_dup_sku_returns_409(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    await _create_module(api_client, auth_headers, sku="MOD-AAA")
    other = await _create_module(api_client, auth_headers, sku="MOD-BBB")
    response = await api_client.patch(
        f"/api/v1/modules/{other['id']}",
        headers=auth_headers,
        json={"sku": "MOD-AAA"},
    )
    assert response.status_code == 409


async def test_delete_then_get_404(api_client: AsyncClient, auth_headers: dict[str, str]) -> None:
    created = await _create_module(api_client, auth_headers)
    response = await api_client.delete(f"/api/v1/modules/{created['id']}", headers=auth_headers)
    assert response.status_code == 204
    response = await api_client.get(f"/api/v1/modules/{created['id']}", headers=auth_headers)
    assert response.status_code == 404


async def test_delete_unknown_returns_404(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    response = await api_client.delete(
        "/api/v1/modules/00000000-0000-0000-0000-000000000000",
        headers=auth_headers,
    )
    assert response.status_code == 404


# ---------- children + cycle + XOR + duplicate ----------


async def test_add_child_component(
    api_client: AsyncClient,
    auth_headers: dict[str, str],
    seeded_components_catalogue: list[Component],
) -> None:
    module = await _create_module(api_client, auth_headers)
    component = seeded_components_catalogue[0]
    response = await api_client.post(
        f"/api/v1/modules/{module['id']}/children",
        headers=auth_headers,
        json={"child_component_id": str(component.id), "quantity": 3},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["child_component_id"] == str(component.id)
    assert body["quantity"] == 3
    assert body["child_component"]["mpn"] == component.mpn


async def test_add_child_xor_violation(
    api_client: AsyncClient,
    auth_headers: dict[str, str],
    seeded_components_catalogue: list[Component],
) -> None:
    module = await _create_module(api_client, auth_headers)
    other = await _create_module(api_client, auth_headers, sku="MOD-OTHER")
    component = seeded_components_catalogue[0]
    response = await api_client.post(
        f"/api/v1/modules/{module['id']}/children",
        headers=auth_headers,
        json={
            "child_component_id": str(component.id),
            "child_module_id": other["id"],
            "quantity": 1,
        },
    )
    assert response.status_code == 422


async def test_add_child_duplicate_returns_422(
    api_client: AsyncClient,
    auth_headers: dict[str, str],
    seeded_components_catalogue: list[Component],
) -> None:
    module = await _create_module(api_client, auth_headers)
    component = seeded_components_catalogue[0]
    body = {"child_component_id": str(component.id), "quantity": 1}
    response = await api_client.post(
        f"/api/v1/modules/{module['id']}/children", headers=auth_headers, json=body
    )
    assert response.status_code == 201
    response = await api_client.post(
        f"/api/v1/modules/{module['id']}/children", headers=auth_headers, json=body
    )
    assert response.status_code == 422
    assert response.json()["code"] == "CHILD_ALREADY_PRESENT"


async def test_add_child_invalid_module_id(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    module = await _create_module(api_client, auth_headers)
    response = await api_client.post(
        f"/api/v1/modules/{module['id']}/children",
        headers=auth_headers,
        json={
            "child_module_id": "00000000-0000-0000-0000-000000000000",
            "quantity": 1,
        },
    )
    assert response.status_code == 422
    assert response.json()["code"] == "INVALID_CHILD_REFERENCE"


async def test_add_child_cycle_detection_direct(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    a = await _create_module(api_client, auth_headers, sku="MOD-CYC-A")
    response = await api_client.post(
        f"/api/v1/modules/{a['id']}/children",
        headers=auth_headers,
        json={"child_module_id": a["id"], "quantity": 1},
    )
    assert response.status_code == 422
    assert response.json()["code"] == "MODULE_CYCLE_DETECTED"


async def test_add_child_cycle_detection_transitive(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    # A → B; trying to add A as a child of B closes a cycle.
    a = await _create_module(api_client, auth_headers, sku="MOD-CYC-AA")
    b = await _create_module(api_client, auth_headers, sku="MOD-CYC-BB")
    response = await api_client.post(
        f"/api/v1/modules/{a['id']}/children",
        headers=auth_headers,
        json={"child_module_id": b["id"], "quantity": 1},
    )
    assert response.status_code == 201
    response = await api_client.post(
        f"/api/v1/modules/{b['id']}/children",
        headers=auth_headers,
        json={"child_module_id": a["id"], "quantity": 1},
    )
    assert response.status_code == 422
    assert response.json()["code"] == "MODULE_CYCLE_DETECTED"


async def test_patch_child_quantity(
    api_client: AsyncClient,
    auth_headers: dict[str, str],
    seeded_components_catalogue: list[Component],
) -> None:
    module = await _create_module(api_client, auth_headers)
    component = seeded_components_catalogue[0]
    add = await api_client.post(
        f"/api/v1/modules/{module['id']}/children",
        headers=auth_headers,
        json={"child_component_id": str(component.id), "quantity": 1},
    )
    edge = add.json()
    response = await api_client.patch(
        f"/api/v1/modules/{module['id']}/children/{edge['id']}",
        headers=auth_headers,
        json={"quantity": 5},
    )
    assert response.status_code == 200
    assert response.json()["quantity"] == 5


async def test_patch_child_quantity_invalid_returns_422(
    api_client: AsyncClient,
    auth_headers: dict[str, str],
    seeded_components_catalogue: list[Component],
) -> None:
    module = await _create_module(api_client, auth_headers)
    component = seeded_components_catalogue[0]
    add = await api_client.post(
        f"/api/v1/modules/{module['id']}/children",
        headers=auth_headers,
        json={"child_component_id": str(component.id), "quantity": 1},
    )
    edge = add.json()
    # quantity < 1 fails Pydantic validation upstream (422).
    response = await api_client.patch(
        f"/api/v1/modules/{module['id']}/children/{edge['id']}",
        headers=auth_headers,
        json={"quantity": 0},
    )
    assert response.status_code == 422


async def test_patch_child_unknown_edge_returns_404(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    module = await _create_module(api_client, auth_headers)
    response = await api_client.patch(
        f"/api/v1/modules/{module['id']}/children/00000000-0000-0000-0000-000000000000",
        headers=auth_headers,
        json={"quantity": 2},
    )
    assert response.status_code == 404


async def test_patch_child_updates_notes_and_sort_order(
    api_client: AsyncClient,
    auth_headers: dict[str, str],
    seeded_components_catalogue: list[Component],
) -> None:
    module = await _create_module(api_client, auth_headers)
    component = seeded_components_catalogue[0]
    add = await api_client.post(
        f"/api/v1/modules/{module['id']}/children",
        headers=auth_headers,
        json={"child_component_id": str(component.id), "quantity": 1},
    )
    edge = add.json()
    response = await api_client.patch(
        f"/api/v1/modules/{module['id']}/children/{edge['id']}",
        headers=auth_headers,
        json={"notes": "hot-swap candidate", "sort_order": 5},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["notes"] == "hot-swap candidate"
    assert body["sort_order"] == 5


async def test_remove_child_idempotent(
    api_client: AsyncClient,
    auth_headers: dict[str, str],
    seeded_components_catalogue: list[Component],
) -> None:
    module = await _create_module(api_client, auth_headers)
    component = seeded_components_catalogue[0]
    add = await api_client.post(
        f"/api/v1/modules/{module['id']}/children",
        headers=auth_headers,
        json={"child_component_id": str(component.id), "quantity": 1},
    )
    edge_id = add.json()["id"]
    response = await api_client.delete(
        f"/api/v1/modules/{module['id']}/children/{edge_id}", headers=auth_headers
    )
    assert response.status_code == 204
    # Idempotent: deleting again still returns 204.
    response = await api_client.delete(
        f"/api/v1/modules/{module['id']}/children/{edge_id}", headers=auth_headers
    )
    assert response.status_code == 204


# ---------- aggregates ----------


async def test_get_detail_hydrates_aggregates(
    api_client: AsyncClient,
    auth_headers: dict[str, str],
    seeded_components_catalogue: list[Component],
) -> None:
    module = await _create_module(api_client, auth_headers, stock=10)
    # Add two components: the worst NATO (D) and the most critical tier (1)
    # both come from the seeded ESP32 + STM32.
    esp = next(c for c in seeded_components_catalogue if c.mpn == "ESP32-WROOM-32")
    stm = next(c for c in seeded_components_catalogue if c.mpn == "STM32F407VGT6")
    await api_client.post(
        f"/api/v1/modules/{module['id']}/children",
        headers=auth_headers,
        json={"child_component_id": str(esp.id), "quantity": 1},
    )
    await api_client.post(
        f"/api/v1/modules/{module['id']}/children",
        headers=auth_headers,
        json={"child_component_id": str(stm.id), "quantity": 1},
    )

    response = await api_client.get(f"/api/v1/modules/{module['id']}", headers=auth_headers)
    body = response.json()
    # Worst NATO across {D, A+} is D; worst tier across {1, 1} is 1.
    assert body["aggregated_nato_score"] == "D"
    assert body["aggregated_tier"] == 1
    assert len(body["children"]) == 2
    # Parents list is empty for a root module.
    assert body["parents"] == []


async def test_parents_list_populated_for_subchild(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    parent = await _create_module(api_client, auth_headers, sku="MOD-P")
    child = await _create_module(api_client, auth_headers, sku="MOD-C")
    await api_client.post(
        f"/api/v1/modules/{parent['id']}/children",
        headers=auth_headers,
        json={"child_module_id": child["id"], "quantity": 1},
    )
    response = await api_client.get(f"/api/v1/modules/{child['id']}", headers=auth_headers)
    body = response.json()
    assert len(body["parents"]) == 1
    assert body["parents"][0]["sku"] == "MOD-P"


# ---------- price history ----------


async def test_price_history_empty_when_no_descendants(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    module = await _create_module(api_client, auth_headers)
    response = await api_client.get(
        f"/api/v1/modules/{module['id']}/price-history", headers=auth_headers
    )
    assert response.status_code == 200
    assert response.json()["series"] == []


# ---------- delete cascades children ----------


async def test_list_module_stock_events_empty(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    module = await _create_module(api_client, auth_headers)
    response = await api_client.get(
        f"/api/v1/modules/{module['id']}/stock-events", headers=auth_headers
    )
    assert response.status_code == 200
    assert response.json()["items"] == []


async def test_list_module_stock_events_unknown_returns_404(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    response = await api_client.get(
        "/api/v1/modules/00000000-0000-0000-0000-000000000000/stock-events",
        headers=auth_headers,
    )
    assert response.status_code == 404


async def test_component_purchases_summary_empty_module(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    module = await _create_module(api_client, auth_headers)
    response = await api_client.get(
        f"/api/v1/modules/{module['id']}/component-purchases-summary",
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json() == []


async def test_component_purchases_summary_unknown_returns_404(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    response = await api_client.get(
        "/api/v1/modules/00000000-0000-0000-0000-000000000000/component-purchases-summary",
        headers=auth_headers,
    )
    assert response.status_code == 404


async def test_delete_module_cascades_children(
    api_client: AsyncClient,
    auth_headers: dict[str, str],
    seeded_components_catalogue: list[Component],
) -> None:
    module = await _create_module(api_client, auth_headers)
    component = seeded_components_catalogue[0]
    await api_client.post(
        f"/api/v1/modules/{module['id']}/children",
        headers=auth_headers,
        json={"child_component_id": str(component.id), "quantity": 1},
    )
    response = await api_client.delete(f"/api/v1/modules/{module['id']}", headers=auth_headers)
    assert response.status_code == 204
    # Component itself still exists (CASCADE removes only the edge).
    response = await api_client.get(f"/api/v1/components/{component.id}", headers=auth_headers)
    assert response.status_code == 200
