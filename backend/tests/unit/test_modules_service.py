"""Unit tests for `ModuleService` helpers — pure logic, no DB."""

from __future__ import annotations

from uuid import uuid4

from app.application.services.modules_service import (
    NATO_ORDER,
    ModuleService,
    _ComponentRollup,
    _worst_nato_score,
)
from app.domain.entities.module_child import ModuleChild


def test_worst_nato_score_empty() -> None:
    assert _worst_nato_score([]) is None


def test_worst_nato_score_single() -> None:
    assert _worst_nato_score(["A"]) == "A"


def test_worst_nato_score_picks_F_over_others() -> None:
    assert _worst_nato_score(["A+", "F", "B"]) == "F"


def test_worst_nato_score_picks_D_when_no_F() -> None:
    assert _worst_nato_score(["A", "D", "B", "C"]) == "D"


def test_worst_nato_score_all_equal() -> None:
    assert _worst_nato_score(["B", "B", "B"]) == "B"


def test_nato_order_constants() -> None:
    assert NATO_ORDER == ["F", "D", "C", "B", "A", "A+"]


def test_compute_buildable_with_no_children_returns_zero() -> None:
    # _compute_buildable doesn't touch the DB — instantiate the service with
    # a None session to call the static-ish helper.
    svc = ModuleService(session=None)  # type: ignore[arg-type]
    assert svc._compute_buildable([], [], module_stock=99) == 0


def test_compute_buildable_min_over_component_edges() -> None:
    svc = ModuleService(session=None)  # type: ignore[arg-type]
    comp_a, comp_b = uuid4(), uuid4()
    edges = [
        ModuleChild(parent_module_id=uuid4(), child_component_id=comp_a, quantity=2),
        ModuleChild(parent_module_id=uuid4(), child_component_id=comp_b, quantity=5),
    ]
    rollups = [
        (_ComponentRollup(id=comp_a, stock=10, nato_score="A", tier=2), 2),
        (_ComponentRollup(id=comp_b, stock=50, nato_score="A", tier=2), 5),
    ]
    # comp_a: 10 // 2 = 5;  comp_b: 50 // 5 = 10  →  MIN = 5
    assert svc._compute_buildable(edges, rollups, module_stock=0) == 5


def test_compute_buildable_ignores_module_children() -> None:
    """Submodule children currently contribute 0 — the metric reflects only
    direct component edges (see service docstring)."""
    svc = ModuleService(session=None)  # type: ignore[arg-type]
    comp = uuid4()
    sub_module = uuid4()
    edges = [
        ModuleChild(parent_module_id=uuid4(), child_component_id=comp, quantity=1),
        ModuleChild(parent_module_id=uuid4(), child_module_id=sub_module, quantity=1),
    ]
    rollups = [
        (_ComponentRollup(id=comp, stock=12, nato_score="A", tier=2), 1),
    ]
    # The submodule edge is filtered out → MIN over [12] = 12.
    assert svc._compute_buildable(edges, rollups, module_stock=0) == 12
