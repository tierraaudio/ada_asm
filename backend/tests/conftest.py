"""Shared pytest fixtures.

Provides a fresh FastAPI app and an ``httpx.AsyncClient`` per test, plus a
DB-cleaning fixture that runs before every integration test so each test
starts from an empty ``users`` / ``refresh_tokens`` / ``password_reset_tokens``
state.
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
    "DATABASE_URL": "postgresql+asyncpg://ada_asm:ada_asm@localhost:5432/ada_asm",
    "CELERY_BROKER_URL": "redis://localhost:6379/0",
    "CELERY_RESULT_BACKEND": "redis://localhost:6379/1",
    "JWT_SECRET": "test-secret-do-not-use-in-prod",
    "CORS_ORIGINS": "http://localhost:5173",
    # Generous default so the bulk of integration tests are not affected by
    # rate-limiting. The explicit rate-limit test below sets a low value
    # and rebuilds the app.
    "LOGIN_RATE_LIMIT_PER_MINUTE": "1000",
    "PASSWORD_RESET_TOKEN_TTL_SECONDS": "3600",
    "FRONTEND_BASE_URL": "http://localhost:5173",
}
for _key, _value in _TEST_ENV.items():
    os.environ.setdefault(_key, _value)


@pytest.fixture
def app() -> Any:
    """Build a fresh FastAPI app for the current test."""
    from app.api.v1.routers.auth import limiter
    from app.main import create_app

    # Reset rate-limit counters between tests so we never carry state.
    limiter.reset()
    return create_app()


@pytest.fixture
async def api_client(app: Any) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.fixture(autouse=True)
async def _truncate_auth_tables() -> AsyncIterator[None]:
    """Truncate auth tables before each test, then dispose the engine after.

    Pytest-asyncio gives each test its own event loop. The cached async engine
    in ``app.infrastructure.db.session`` is bound to whichever loop first
    built it, so we dispose it after every test to force a fresh engine on
    the next loop.
    """
    from sqlalchemy import text

    from app.infrastructure.db import session as db_session

    factory = db_session.get_session_factory()
    async with factory() as session:
        try:
            await session.execute(
                text(
                    "TRUNCATE TABLE refresh_tokens, "
                    "password_reset_tokens, scoring_alternatives, "
                    "scoring_classifications, component_nato_scorings, "
                    "stock_events, supplier_stocks, supplier_prices, "
                    "components, suppliers, users RESTART IDENTITY CASCADE"
                )
            )
            await session.commit()
        except Exception:
            await session.rollback()

    yield

    # Dispose engine + clear cached factory so the next test rebuilds them
    # against its own event loop.
    if db_session._engine is not None:
        await db_session._engine.dispose()
        db_session._engine = None
        db_session._session_factory = None
