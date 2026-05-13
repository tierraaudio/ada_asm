"""Shared pytest fixtures.

Provides a fresh FastAPI app and an ``httpx.AsyncClient`` per test, with the
test environment populated with safe defaults so we never depend on the
host's real env.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

# Test-only env defaults applied at import time, before any app module reads
# Settings(). Real envs are not modified — these only set values that are
# missing on the test host.
_TEST_ENV: dict[str, str] = {
    "ENV": "development",
    "LOG_LEVEL": "WARNING",
    "DATABASE_URL": "postgresql+asyncpg://test:test@localhost:5432/test",
    "CELERY_BROKER_URL": "redis://localhost:6379/0",
    "CELERY_RESULT_BACKEND": "redis://localhost:6379/1",
    "JWT_SECRET": "test-secret-do-not-use-in-prod",
    "CORS_ORIGINS": "http://localhost:5173",
}
for _key, _value in _TEST_ENV.items():
    os.environ.setdefault(_key, _value)


@pytest.fixture
def app() -> Any:
    """Build a fresh FastAPI app for the current test."""
    from app.main import create_app

    return create_app()


@pytest.fixture
async def api_client(app: Any) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
