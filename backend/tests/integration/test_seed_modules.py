"""Integration tests for ``python -m app.scripts.seed_modules``."""

from __future__ import annotations

import pytest
from sqlalchemy import func, select

from app.infrastructure.db.models.module import ModuleModel
from app.infrastructure.db.models.module_child import ModuleChildModel
from app.infrastructure.db.session import get_session_factory
from app.scripts import seed_components, seed_modules

pytestmark = pytest.mark.integration


async def _count(table: type) -> int:
    factory = get_session_factory()
    async with factory() as session:
        return int((await session.execute(select(func.count(table.id)))).scalar_one())


async def test_seed_refuses_without_components() -> None:
    # No components seeded yet → seed_modules should exit with 3.
    assert await seed_modules._seed(reset=False) == 3


async def test_seed_inserts_modules_and_children() -> None:
    assert await seed_components._seed(reset=False) == 0
    assert await seed_modules._seed(reset=False) == 0

    assert await _count(ModuleModel) == len(seed_modules.SEED_SPECS)

    # Each spec adds its component children + sub-module children.
    expected_edges = sum(
        len(spec.component_children_mpns) + len(spec.sub_module_children_skus)
        for spec in seed_modules.SEED_SPECS
    )
    assert await _count(ModuleChildModel) == expected_edges


async def test_seed_refuses_to_reseed_when_modules_exist() -> None:
    assert await seed_components._seed(reset=False) == 0
    assert await seed_modules._seed(reset=False) == 0
    assert await seed_modules._seed(reset=False) == 2  # refuse


async def test_seed_with_reset_truncates_and_reseeds() -> None:
    assert await seed_components._seed(reset=False) == 0
    assert await seed_modules._seed(reset=False) == 0
    first_count = await _count(ModuleChildModel)
    assert await seed_modules._seed(reset=True) == 0
    assert await _count(ModuleChildModel) == first_count
