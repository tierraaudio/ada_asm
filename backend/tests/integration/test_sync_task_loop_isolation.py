"""Regression test for the Celery prefork event-loop bug.

The daily sync ran each `sync_one_supplier` via `asyncio.run(...)`, but the
cached async engine stayed bound to the FIRST task's loop. A second task on
the same worker process (a new `asyncio.run` loop) then failed with "got
Future attached to a different loop" / "Event loop is closed". This is
exactly what broke the 03:00 cron once there were components to process
(the first manual run worked because the worker was freshly started).

This test simulates two sequential task invocations in one process and
asserts the second succeeds — i.e. the engine is rebuilt per loop.
"""

from __future__ import annotations

import asyncio

import pytest

from app.infrastructure.db import session as db_session
from app.infrastructure.db.session import dispose_engine, forget_engine, get_session_factory


def _run_one() -> int:
    """One task body: open a session, do trivial DB I/O, dispose at the end.

    Mirrors `_run_for_supplier_isolated`: forget any stale engine, build a
    fresh one on THIS loop, use it, dispose it before the loop closes.
    """

    async def _body() -> int:
        forget_engine()
        try:
            factory = get_session_factory()
            async with factory() as s:
                from sqlalchemy import text

                return int((await s.execute(text("SELECT 1"))).scalar_one())
        finally:
            await dispose_engine()

    return asyncio.run(_body())


def test_two_sequential_asyncio_runs_do_not_clash_on_loops() -> None:
    # First invocation (like the 21:47 manual run) — builds the engine.
    assert _run_one() == 1
    # Second invocation on a NEW loop (like the 03:00 cron) — must NOT raise
    # "attached to a different loop" / "Event loop is closed".
    assert _run_one() == 1
    # And a third for good measure.
    assert _run_one() == 1


def test_forget_engine_then_rebuild_gives_fresh_factory() -> None:
    f1 = get_session_factory()
    forget_engine()
    f2 = get_session_factory()
    assert f1 is not f2  # a new factory was built after forgetting
    assert db_session._engine is not None


@pytest.fixture(autouse=True)
def _cleanup_engine() -> None:
    yield
    forget_engine()
