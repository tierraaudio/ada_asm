"""Integration tests for ``python -m app.scripts.seed_components``."""

from __future__ import annotations

import pytest
from sqlalchemy import func, select

from app.application.services.components_service import ComponentsService
from app.domain.repositories.component_repository import ComponentFilters
from app.infrastructure.db.models.component import ComponentModel
from app.infrastructure.db.models.component_purchase import ComponentPurchaseModel
from app.infrastructure.db.session import get_session_factory
from app.infrastructure.repositories.component_purchase_repository import (
    SqlAlchemyComponentPurchaseRepository,
)
from app.infrastructure.repositories.component_repository import (
    SqlAlchemyComponentRepository,
)
from app.scripts import seed_components as seed_module

pytestmark = pytest.mark.integration


async def _count_components() -> int:
    factory = get_session_factory()
    async with factory() as session:
        return int((await session.execute(select(func.count(ComponentModel.id)))).scalar_one())


async def _count_purchases() -> int:
    factory = get_session_factory()
    async with factory() as session:
        return int(
            (await session.execute(select(func.count(ComponentPurchaseModel.id)))).scalar_one()
        )


async def test_seed_inserts_expected_number_of_components_and_purchases() -> None:
    exit_code = await seed_module._seed(reset=False)
    assert exit_code == 0
    assert await _count_components() == len(seed_module.SAMPLE_COMPONENTS)
    # Each component gets 3-6 purchases.
    purchase_count = await _count_purchases()
    assert purchase_count >= 3 * len(seed_module.SAMPLE_COMPONENTS)
    assert purchase_count <= 6 * len(seed_module.SAMPLE_COMPONENTS)


async def test_seed_refuses_to_reseed_when_components_exist() -> None:
    # First run succeeds.
    assert await seed_module._seed(reset=False) == 0
    # Second run without --reset is refused.
    assert await seed_module._seed(reset=False) == 2
    # No duplication occurred.
    assert await _count_components() == len(seed_module.SAMPLE_COMPONENTS)


async def test_seed_with_reset_truncates_and_reseeds() -> None:
    assert await seed_module._seed(reset=False) == 0
    first_count = await _count_purchases()
    # Reset flag should truncate then succeed regardless of existing data.
    assert await seed_module._seed(reset=True) == 0
    assert await _count_components() == len(seed_module.SAMPLE_COMPONENTS)
    # Deterministic seed (`random.seed(42)`) means the new purchase count
    # matches the previous run exactly.
    assert await _count_purchases() == first_count


async def test_seeded_components_are_filterable_through_service() -> None:
    assert await seed_module._seed(reset=False) == 0
    factory = get_session_factory()
    async with factory() as session:
        service = ComponentsService(
            components=SqlAlchemyComponentRepository(session),
            purchases=SqlAlchemyComponentPurchaseRepository(session),
        )
        result = await service.list(
            filters=ComponentFilters(family="Sensores"), page=1, page_size=50
        )
        families = {c.family for c in result.items}
        assert families == {"Sensores"}
        assert result.total >= 1
