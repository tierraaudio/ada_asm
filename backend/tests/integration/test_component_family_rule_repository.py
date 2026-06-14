"""Integration test: the family-rule repository loads the seeded rules."""

from __future__ import annotations

import pytest

from app.infrastructure.db.session import get_session_factory
from app.infrastructure.repositories.component_family_rule_repository import (
    SqlAlchemyComponentFamilyRuleRepository,
)

pytestmark = pytest.mark.asyncio


async def test_list_enabled_returns_seeded_rules() -> None:
    factory = get_session_factory()
    async with factory() as session:
        repo = SqlAlchemyComponentFamilyRuleRepository(session)
        rules = await repo.list_enabled()

    assert rules, "seed migration should have inserted family rules"
    # Spot-check a known seeded rule: DigiKey leaf 280 → Diodos.
    diode = next(
        (
            r
            for r in rules
            if r.supplier == "digikey" and r.match_type == "category_id" and r.match_value == "280"
        ),
        None,
    )
    assert diode is not None
    assert diode.family == "Diodos"
    assert diode.confidence == 100
    # Every loaded rule is enabled.
    assert all(r.enabled for r in rules)
