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
