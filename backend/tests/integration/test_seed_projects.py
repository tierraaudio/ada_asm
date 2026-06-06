"""Integration tests for ``python -m app.scripts.seed_projects``."""

from __future__ import annotations

import pytest
from sqlalchemy import func, select

from app.infrastructure.db.models.customer import CustomerModel
from app.infrastructure.db.models.project import ProjectModel
from app.infrastructure.db.models.project_child import ProjectChildModel
from app.infrastructure.db.models.project_interest_link import (
    ProjectInterestLinkModel,
)
from app.infrastructure.db.session import get_session_factory
from app.scripts import seed_components, seed_modules, seed_projects

pytestmark = pytest.mark.integration


async def _count(table: type) -> int:
    factory = get_session_factory()
    async with factory() as session:
        return int((await session.execute(select(func.count(table.id)))).scalar_one())


async def test_seed_refuses_without_components_or_modules() -> None:
    # Neither components nor modules are seeded yet → seed_projects exits with 3.
    with pytest.raises(SystemExit) as excinfo:
        await seed_projects.seed(reset=False)
    assert excinfo.value.code == 3


async def test_seed_refuses_when_projects_non_empty() -> None:
    # Bootstrap the dependency chain.
    assert await seed_components._seed(reset=False) == 0
    assert await seed_modules._seed(reset=False) == 0
    await seed_projects.seed(reset=False)
    # Second invocation without --reset must exit 2 (DB already has projects).
    with pytest.raises(SystemExit) as excinfo:
        await seed_projects.seed(reset=False)
    assert excinfo.value.code == 2


async def test_seed_inserts_customers_projects_links_and_children() -> None:
    assert await seed_components._seed(reset=False) == 0
    assert await seed_modules._seed(reset=False) == 0
    await seed_projects.seed(reset=False)

    # Counts come from the script's own catalogues.
    expected_customers = len(seed_projects._CUSTOMERS)
    expected_projects = len(seed_projects._PROJECTS)
    expected_links = sum(len(p.interest_links) for p in seed_projects._PROJECTS)
    expected_children = sum(len(p.bom) for p in seed_projects._PROJECTS)

    assert await _count(CustomerModel) == expected_customers
    assert await _count(ProjectModel) == expected_projects
    assert await _count(ProjectInterestLinkModel) == expected_links
    assert await _count(ProjectChildModel) == expected_children


async def test_seed_with_reset_is_idempotent() -> None:
    assert await seed_components._seed(reset=False) == 0
    assert await seed_modules._seed(reset=False) == 0
    await seed_projects.seed(reset=False)
    # Re-seed with --reset wipes + replays without conflict.
    await seed_projects.seed(reset=True)
    assert await _count(ProjectModel) == len(seed_projects._PROJECTS)
