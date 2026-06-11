"""Unit tests for the Redis token-bucket rate limiter.

Uses fakeredis-async with a real Lua interpreter so the limiter's atomic
script runs unmodified — the only thing we swap is the network round-trip.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import fakeredis.aioredis
import pytest
import pytest_asyncio
from redis import exceptions as redis_exceptions

from app.core.exceptions import SupplierRateLimitedError
from app.infrastructure import rate_limit

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def fake_redis() -> AsyncIterator[fakeredis.aioredis.FakeRedis]:
    """Provide a fresh fakeredis client, wired into the limiter for the test."""
    client = fakeredis.aioredis.FakeRedis(decode_responses=True)
    rate_limit._set_client(client)
    try:
        yield client
    finally:
        await client.aclose()
        rate_limit._set_client(None)


async def test_acquire_under_quota_returns_immediately(
    fake_redis: fakeredis.aioredis.FakeRedis,
) -> None:
    # Capacity = 60 tokens / minute → first call consumes 1 of 60.
    await rate_limit.acquire("test:plenty", limit_per_minute=60)
    # And many more should still pass without blocking.
    for _ in range(20):
        await rate_limit.acquire("test:plenty", limit_per_minute=60)


async def test_acquire_zero_or_negative_limit_rejects(
    fake_redis: fakeredis.aioredis.FakeRedis,
) -> None:
    with pytest.raises(ValueError):
        await rate_limit.acquire("test:zero", limit_per_minute=0)
    with pytest.raises(ValueError):
        await rate_limit.acquire("test:neg", limit_per_minute=-5)


async def test_acquire_blocks_when_over_quota(
    fake_redis: fakeredis.aioredis.FakeRedis,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When the bucket is empty, `acquire` sleeps until the next token. We
    don't actually want to sleep in the test, so we patch `asyncio.sleep`
    to a no-op and advance the simulated clock by hand via `time.time`."""

    slept_ms: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        slept_ms.append(seconds * 1000)
        # Advance the clock so the next Lua refill sees enough elapsed ms.
        nonlocal current_ms
        current_ms += int(seconds * 1000)

    current_ms = 1_700_000_000_000  # arbitrary epoch ms

    def fake_time_seconds() -> float:
        return current_ms / 1000.0

    monkeypatch.setattr("app.infrastructure.rate_limit.asyncio.sleep", fake_sleep)
    monkeypatch.setattr("app.infrastructure.rate_limit.time.time", fake_time_seconds)

    # Drain the bucket: 6 tokens at 6/min.
    for _ in range(6):
        await rate_limit.acquire("test:burst", limit_per_minute=6)
    assert slept_ms == [], "first 6 calls should not have slept"

    # 7th call must wait ≈ 10_000 ms (60_000 ms / 6 tokens/min).
    await rate_limit.acquire("test:burst", limit_per_minute=6)
    assert len(slept_ms) == 1
    assert 9_500 <= slept_ms[0] <= 10_500


async def test_acquire_raises_when_pathological_wait_exceeds_cap(
    fake_redis: fakeredis.aioredis.FakeRedis,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Defensive: if the Lua script reports a wait > 60 000 ms in a single
    call (clock skew, capacity misconfig, etc.), `acquire` must raise
    `SupplierRateLimitedError` instead of blocking forever."""

    async def fake_eval(*_args: object, **_kwargs: object) -> int:
        return 90_000  # 90 s — beyond the cap

    monkeypatch.setattr(fake_redis, "eval", fake_eval)

    async def fake_sleep(_seconds: float) -> None:
        # Should never be called once we exceed the cap.
        raise AssertionError("should not sleep when wait exceeds cap")

    monkeypatch.setattr("app.infrastructure.rate_limit.asyncio.sleep", fake_sleep)

    with pytest.raises(SupplierRateLimitedError):
        await rate_limit.acquire("test:pathological", limit_per_minute=10)


async def test_separate_buckets_are_independent(
    fake_redis: fakeredis.aioredis.FakeRedis,
) -> None:
    # Drain bucket A; bucket B must still have full capacity.
    for _ in range(5):
        await rate_limit.acquire("test:a", limit_per_minute=5)
    for _ in range(5):
        await rate_limit.acquire("test:b", limit_per_minute=5)


class _DeadRedis:
    """Client whose every command fails with a connectivity error —
    simulates Redis being unreachable through the CAE internal ingress."""

    async def eval(self, *args: object, **kwargs: object) -> int:
        raise redis_exceptions.ConnectionError("connection refused")


async def test_acquire_fails_open_when_redis_unreachable() -> None:
    """Rate limiting is a protection, not a dependency: if Redis is down
    the caller proceeds unthrottled instead of failing the request."""

    rate_limit._set_client(_DeadRedis())  # type: ignore[arg-type]
    try:
        await rate_limit.acquire("test:dead", limit_per_minute=30)
    finally:
        rate_limit._set_client(None)
