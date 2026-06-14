"""Unit tests for `ProjectService` pure helpers — no DB."""

from __future__ import annotations

from datetime import date
from uuid import uuid4

from app.application.services.projects_service import (
    AddProjectChildInput,
    ProjectCreate,
    ProjectUpdate,
    UpdateProjectChildInput,
    _ComponentRollup,
)


def test_project_create_dataclass_defaults() -> None:
    p = ProjectCreate(code="X-1", name="Test")
    assert p.code == "X-1"
    assert p.name == "Test"
    assert p.status == "Presupuestado"
    assert p.tags is None
    assert p.customer_id is None
    assert p.fecha_entrega_real is None


def test_project_create_dataclass_full() -> None:
    cid = uuid4()
    p = ProjectCreate(
        code="X-2",
        name="Full",
        description="d",
        status="En proceso",
        customer_id=cid,
        icon="🚀",
        color="#ff0000",
        tags=["a"],
        version="v1",
        fecha_inicio=date(2026, 1, 1),
        fecha_entrega_estimada=date(2026, 6, 1),
        fecha_entrega_real=date(2026, 7, 1),
        notas="n",
    )
    assert p.customer_id == cid
    assert p.tags == ["a"]
    assert p.fecha_entrega_real == date(2026, 7, 1)


def test_project_update_dataclass_all_none_by_default() -> None:
    upd = ProjectUpdate()
    # All fields default to None to make "missing" detection trivial.
    for field in (
        upd.code,
        upd.name,
        upd.description,
        upd.status,
        upd.customer_id,
        upd.icon,
        upd.color,
        upd.tags,
        upd.version,
        upd.fecha_inicio,
        upd.fecha_entrega_estimada,
        upd.fecha_entrega_real,
        upd.notas,
    ):
        assert field is None


def test_add_project_child_input_defaults() -> None:
    inp = AddProjectChildInput()
    assert inp.child_module_id is None
    assert inp.child_component_id is None
    assert inp.quantity == 1
    assert inp.notes is None
    assert inp.sort_order == 0


def test_update_project_child_input_defaults() -> None:
    inp = UpdateProjectChildInput()
    assert inp.quantity is None
    assert inp.notes is None
    assert inp.sort_order is None


def test_component_rollup_defaults_expires_at_to_none() -> None:
    cid = uuid4()
    r = _ComponentRollup(id=cid, stock=5, nato_score="A", tier=1)
    assert r.id == cid
    assert r.stock == 5
    assert r.expires_at is None


def test_component_rollup_with_explicit_expires_at() -> None:
    cid = uuid4()
    expiry = date(2026, 12, 31)
    r = _ComponentRollup(id=cid, stock=10, nato_score="D", tier=3, expires_at=expiry)
    assert r.expires_at == expiry
    assert r.tier == 3
