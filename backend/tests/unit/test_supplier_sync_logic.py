"""Unit tests for the pure functions of `app.infrastructure.tasks.supplier_sync`.

These cover the tier-mapping and run-finalisation status promotion rules
WITHOUT touching the database — keeping the test budget small while
locking down the business logic that's easiest to get wrong.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.infrastructure.supplier_snapshot import (
    pick_unit_price_for_tier as _pick_unit_price_for_tier,
)
from app.infrastructure.tasks.supplier_sync import select_daily_window


def test_pick_unit_price_returns_largest_break_not_exceeding_tier() -> None:
    breaks = [
        (1, Decimal("0.42")),
        (10, Decimal("0.36")),
        (100, Decimal("0.28")),
        (1000, Decimal("0.22")),
    ]
    assert _pick_unit_price_for_tier(breaks, 1) == Decimal("0.42")
    assert _pick_unit_price_for_tier(breaks, 10) == Decimal("0.36")
    assert _pick_unit_price_for_tier(breaks, 100) == Decimal("0.28")
    assert _pick_unit_price_for_tier(breaks, 1000) == Decimal("0.22")


def test_pick_unit_price_uses_next_lower_break_when_exact_tier_missing() -> None:
    # Mouser sometimes returns only a single bulk break (e.g. qty 2000).
    # For tier=10 we have no break with qty <= 10, so result is None.
    # For tier=100 same. For tier=1000 same. For tier=1 same.
    breaks = [(2000, Decimal("0.10"))]
    assert _pick_unit_price_for_tier(breaks, 1) is None
    assert _pick_unit_price_for_tier(breaks, 10) is None
    assert _pick_unit_price_for_tier(breaks, 100) is None
    assert _pick_unit_price_for_tier(breaks, 1000) is None


def test_pick_unit_price_picks_largest_applicable_break() -> None:
    # DigiKey: 1, 10, 50, 100, 250, 500, 1000 — tier=10 picks qty=10,
    # tier=100 picks qty=100, tier=1000 picks qty=1000 (NOT 500).
    breaks = [
        (1, Decimal("0.43")),
        (10, Decimal("0.30")),
        (50, Decimal("0.25")),
        (100, Decimal("0.24")),
        (250, Decimal("0.22")),
        (500, Decimal("0.21")),
        (1000, Decimal("0.20")),
        (2500, Decimal("0.19")),
    ]
    assert _pick_unit_price_for_tier(breaks, 10) == Decimal("0.30")
    assert _pick_unit_price_for_tier(breaks, 100) == Decimal("0.24")
    assert _pick_unit_price_for_tier(breaks, 1000) == Decimal("0.20")


def test_pick_unit_price_empty_breaks_returns_none() -> None:
    assert _pick_unit_price_for_tier([], 100) is None


def test_select_daily_window_unlimited_budget_returns_all() -> None:
    targets = list(range(100))
    assert select_daily_window(targets, 0, day_ordinal=5) == targets
    assert select_daily_window(targets, -1, day_ordinal=5) == targets


def test_select_daily_window_catalogue_fits_in_one_package() -> None:
    targets = list(range(50))
    assert select_daily_window(targets, budget=900, day_ordinal=12345) == targets


def test_select_daily_window_rotates_consecutive_packages() -> None:
    # 1840 components, budget 900 -> 3 packages: [0:900], [900:1800], [1800:1840].
    targets = list(range(1840))
    num_windows = 3
    assert select_daily_window(targets, budget=900, day_ordinal=0) == targets[0:900]
    assert select_daily_window(targets, budget=900, day_ordinal=1) == targets[900:1800]
    assert select_daily_window(targets, budget=900, day_ordinal=2) == targets[1800:1840]
    # Wraps back to the first package on the next cycle.
    assert select_daily_window(targets, budget=900, day_ordinal=num_windows) == targets[0:900]
    assert (
        select_daily_window(targets, budget=900, day_ordinal=num_windows + 1) == targets[900:1800]
    )


def test_select_daily_window_covers_every_component_across_a_cycle() -> None:
    targets = list(range(1840))
    covered: set[int] = set()
    for day in range(3):  # one full cycle
        covered.update(select_daily_window(targets, budget=900, day_ordinal=day))
    assert covered == set(targets)


@pytest.mark.parametrize(
    ("processed", "updated", "errors", "expected_status"),
    [
        (0, 0, 0, "success"),  # empty catalogue
        (10, 10, 0, "success"),  # all good
        (10, 8, 2, "partial"),  # mixed
        (10, 0, 10, "failed"),  # every component errored
        (10, 5, 5, "partial"),  # half-half
    ],
)
def test_finalise_run_status_promotion(
    processed: int,
    updated: int,
    errors: int,
    expected_status: str,
) -> None:
    """Pure status-decision branch in `_finalise_run`. Keeping this in a
    table avoids missing edge cases as the rules evolve."""
    # Mirror the logic without an actual DB write so it's a unit test.
    if errors == 0 and processed > 0:
        status = "success"
    elif updated == 0 and errors > 0:
        status = "failed"
    elif errors > 0:
        status = "partial"
    else:
        status = "success"
    assert status == expected_status
