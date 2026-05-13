"""Integration-test fixtures.

Provides ``seeded_user`` and ``seeded_admin`` factory fixtures backed by the
running PostgreSQL container.
"""

from __future__ import annotations

from typing import Literal

import pytest

from app.domain.entities.user import User
from app.infrastructure.db.session import get_session_factory
from app.infrastructure.repositories.user_repository import SqlAlchemyUserRepository
from app.infrastructure.security import hash_password


async def _seed(
    *,
    email: str = "alice@example.com",
    password: str = "long-enough-passphrase",
    full_name: str = "Alice Test",
    role: Literal["admin", "user"] = "user",
    is_active: bool = True,
) -> User:
    factory = get_session_factory()
    async with factory() as session:
        repo = SqlAlchemyUserRepository(session)
        user = User(
            email=email,
            password_hash=hash_password(password),
            full_name=full_name,
            global_role=role,
            is_active=is_active,
        )
        saved = await repo.save(user)
        await session.commit()
        return saved


@pytest.fixture
async def seeded_user() -> User:
    return await _seed()


@pytest.fixture
async def seeded_admin() -> User:
    return await _seed(
        email="admin@example.com",
        password="admin-long-passphrase",
        full_name="Admin Test",
        role="admin",
    )


@pytest.fixture
async def seeded_inactive() -> User:
    return await _seed(
        email="ghost@example.com",
        password="ghost-long-passphrase",
        is_active=False,
    )
