"""Integration tests for the customers surface.

Covers list / create / get / patch / delete for `/api/v1/customers`, including
the case-insensitive `holded_id` uniqueness, the 404 paths, the partial-update
behaviour (including nulling optional fields), and the FK SET NULL effect on
projects when a customer is removed.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.integration


async def _create_customer(
    api_client: AsyncClient, headers: dict[str, str], **overrides: object
) -> dict:
    body = {
        "holded_id": "HOLD-001",
        "name": "Acme Robotics",
        **overrides,
    }
    response = await api_client.post("/api/v1/customers", headers=headers, json=body)
    assert response.status_code == 201, response.text
    return response.json()


# ---------- list ----------


async def test_list_empty(api_client: AsyncClient, auth_headers: dict[str, str]) -> None:
    response = await api_client.get("/api/v1/customers", headers=auth_headers)
    assert response.status_code == 200
    assert response.json() == []


async def test_list_requires_auth(api_client: AsyncClient) -> None:
    response = await api_client.get("/api/v1/customers")
    assert response.status_code == 401


async def test_create_then_list_sorted_by_name(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    await _create_customer(
        api_client, auth_headers, holded_id="HOLD-Z", name="Zen Robotics"
    )
    await _create_customer(
        api_client, auth_headers, holded_id="HOLD-A", name="Acme Robotics"
    )
    response = await api_client.get("/api/v1/customers", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert [c["name"] for c in body] == ["Acme Robotics", "Zen Robotics"]


# ---------- create ----------


async def test_create_with_full_payload(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    response = await api_client.post(
        "/api/v1/customers",
        headers=auth_headers,
        json={
            "holded_id": "HOLD-FULL",
            "name": "Full Customer",
            "holded_url": "https://app.holded.com/contacts/abc",
            "notas": "Long-term partner.",
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["holded_id"] == "HOLD-FULL"
    assert body["holded_url"] == "https://app.holded.com/contacts/abc"
    assert body["notas"] == "Long-term partner."


async def test_create_dup_holded_id_case_insensitive_returns_409(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    await _create_customer(api_client, auth_headers, holded_id="HOLD-DUP")
    response = await api_client.post(
        "/api/v1/customers",
        headers=auth_headers,
        json={"holded_id": "hold-dup", "name": "Same id, different case"},
    )
    assert response.status_code == 409
    assert response.json()["code"] == "CUSTOMER_HOLDED_ID_ALREADY_REGISTERED"


async def test_create_validation_error_missing_fields(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    response = await api_client.post(
        "/api/v1/customers",
        headers=auth_headers,
        json={"holded_id": "", "name": ""},
    )
    assert response.status_code == 422


# ---------- get ----------


async def test_get_existing(api_client: AsyncClient, auth_headers: dict[str, str]) -> None:
    created = await _create_customer(api_client, auth_headers)
    response = await api_client.get(
        f"/api/v1/customers/{created['id']}", headers=auth_headers
    )
    assert response.status_code == 200
    assert response.json()["id"] == created["id"]


async def test_get_404(api_client: AsyncClient, auth_headers: dict[str, str]) -> None:
    response = await api_client.get(
        "/api/v1/customers/00000000-0000-0000-0000-000000000000",
        headers=auth_headers,
    )
    assert response.status_code == 404
    assert response.json()["code"] == "CUSTOMER_NOT_FOUND"


# ---------- patch ----------


async def test_patch_updates_partial_fields(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    created = await _create_customer(api_client, auth_headers)
    response = await api_client.patch(
        f"/api/v1/customers/{created['id']}",
        headers=auth_headers,
        json={"name": "Renamed Co"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Renamed Co"
    assert body["holded_id"] == created["holded_id"]


async def test_patch_updates_all_optional_fields(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    created = await _create_customer(api_client, auth_headers)
    response = await api_client.patch(
        f"/api/v1/customers/{created['id']}",
        headers=auth_headers,
        json={
            "holded_id": "HOLD-UPDATED",
            "name": "Updated Name",
            "holded_url": "https://app.holded.com/contacts/xyz",
            "notas": "Updated notes",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["holded_id"] == "HOLD-UPDATED"
    assert body["name"] == "Updated Name"
    assert body["holded_url"] == "https://app.holded.com/contacts/xyz"
    assert body["notas"] == "Updated notes"


async def test_patch_clears_optional_nullable_fields(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    created = await _create_customer(
        api_client,
        auth_headers,
        holded_url="https://app.holded.com/contacts/abc",
        notas="present",
    )
    # `holded_url` and `notas` are nullable optional fields — explicit null
    # clears them (the router treats them as explicitly set when in fields_set).
    response = await api_client.patch(
        f"/api/v1/customers/{created['id']}",
        headers=auth_headers,
        json={"holded_url": None, "notas": None},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["holded_url"] is None
    assert body["notas"] is None


async def test_patch_404_when_unknown(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    response = await api_client.patch(
        "/api/v1/customers/00000000-0000-0000-0000-000000000000",
        headers=auth_headers,
        json={"name": "Ghost"},
    )
    assert response.status_code == 404


# ---------- delete ----------


async def test_delete_then_get_404(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    created = await _create_customer(api_client, auth_headers)
    response = await api_client.delete(
        f"/api/v1/customers/{created['id']}", headers=auth_headers
    )
    assert response.status_code == 204
    response = await api_client.get(
        f"/api/v1/customers/{created['id']}", headers=auth_headers
    )
    assert response.status_code == 404


async def test_delete_unknown_is_no_op(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    """Repo delete is idempotent — unknown id still returns 204."""
    response = await api_client.delete(
        "/api/v1/customers/00000000-0000-0000-0000-000000000000",
        headers=auth_headers,
    )
    assert response.status_code == 204


async def test_delete_customer_nullifies_project_customer_id(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    """The customers→projects FK is ON DELETE SET NULL: projects survive."""
    customer = await _create_customer(api_client, auth_headers)
    # Create a project linked to that customer.
    project = await api_client.post(
        "/api/v1/projects",
        headers=auth_headers,
        json={
            "code": "PRJ-CUST-LINK",
            "name": "Linked project",
            "customer_id": customer["id"],
        },
    )
    assert project.status_code == 201, project.text
    project_id = project.json()["id"]

    # Delete the customer.
    delete = await api_client.delete(
        f"/api/v1/customers/{customer['id']}", headers=auth_headers
    )
    assert delete.status_code == 204

    # Project still exists; customer_id was set to null by the FK action.
    detail = await api_client.get(
        f"/api/v1/projects/{project_id}", headers=auth_headers
    )
    assert detail.status_code == 200
    assert detail.json()["customer_id"] is None
    assert detail.json()["customer"] is None
