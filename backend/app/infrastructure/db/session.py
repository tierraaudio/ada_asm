"""Async SQLAlchemy engine + session factory.

The engine is built lazily on first use so importing this module is safe at
import time (e.g. in Celery task modules) even before settings are valid.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def _build() -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    settings = get_settings()
    engine = create_async_engine(
        settings.database_url,
        echo=False,
        pool_pre_ping=True,
        future=True,
    )
    factory = async_sessionmaker(
        engine,
        expire_on_commit=False,
        autoflush=False,
    )
    return engine, factory


def get_engine() -> AsyncEngine:
    global _engine, _session_factory
    if _engine is None:
        _engine, _session_factory = _build()
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _engine, _session_factory
    if _session_factory is None:
        _engine, _session_factory = _build()
    return _session_factory


def forget_engine() -> None:
    """Drop the cached engine reference WITHOUT disposing it.

    Celery prefork workers run each task on a fresh ``asyncio.run`` loop, but
    the cached async engine is bound to the loop of the FIRST task that built
    it. On a later task that loop is closed, so its pooled asyncpg
    connections raise "got Future attached to a different loop" /
    "Event loop is closed". A task calls this at the start to abandon any
    stale engine so the next ``get_session_factory()`` rebuilds one on the
    current loop. The stale engine is GC'd (its connections are already dead
    with the closed loop, so there is nothing to await-dispose).
    """
    global _engine, _session_factory
    _engine = None
    _session_factory = None


async def dispose_engine() -> None:
    """Dispose the cached engine on the CURRENT loop and clear the cache.

    Called at the end of a Celery task (inside the same ``asyncio.run`` loop
    that built the engine) so connections are returned cleanly before the
    loop closes — preventing the next task from inheriting a dead-loop pool.
    """
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _session_factory = None


async def get_db_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency that yields one session per request.

    Commits on successful exit, rolls back on any exception. Handlers do not
    call ``session.commit()`` directly — that is this function's
    responsibility, so write paths are atomic per request.
    """
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
