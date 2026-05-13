"""Integration tests for ``python -m app.scripts.seed_admin``."""

from __future__ import annotations

import pytest

from app.infrastructure.db.session import get_session_factory
from app.infrastructure.repositories.user_repository import SqlAlchemyUserRepository
from app.scripts.seed_admin import _seed

pytestmark = pytest.mark.integration


async def test_seed_admin_creates_user_when_no_admin_exists() -> None:
    exit_code = await _seed("founder@example.com", "long-passphrase-here", "Founder")
    assert exit_code == 0

    factory = get_session_factory()
    async with factory() as session:
        repo = SqlAlchemyUserRepository(session)
        admins = await repo.list_admins()

    emails = [u.email for u in admins]
    assert "founder@example.com" in emails


async def test_seed_admin_refuses_when_admin_already_exists() -> None:
    await _seed("first-admin@example.com", "long-passphrase-here", "First")

    exit_code = await _seed("second-admin@example.com", "long-passphrase-here", "Second")
    assert exit_code == 2

    factory = get_session_factory()
    async with factory() as session:
        repo = SqlAlchemyUserRepository(session)
        admins = await repo.list_admins()
    emails = {u.email for u in admins}
    assert "first-admin@example.com" in emails
    assert "second-admin@example.com" not in emails
