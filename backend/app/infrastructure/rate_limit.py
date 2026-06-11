"""Redis-backed token-bucket rate limiter.

Shared by every `SupplierAdapter` so a per-process limiter (which would
miss the fan-out across Celery workers) is not used. The bucket is keyed
by `rate_limit:<bucket>`; one bucket per supplier code is recommended:

    await acquire("supplier:mouser", limit_per_minute=30)

Algorithm: classic token bucket. Capacity = `limit_per_minute`; refill
rate = `limit_per_minute / 60` tokens per second. On `acquire`:

1. The Lua script (atomic in Redis) refills the bucket based on elapsed
   wall time, consumes 1 token if available, and returns 0.
2. If no token is available, the script returns the milliseconds the
   caller must wait for the next token. The async helper sleeps that
   long, then retries the script. A hard cap of 60_000 ms per single
   call protects against pathological starvation.

The bucket's TTL is set to 2x the refill period to garbage-collect
inactive buckets without affecting correctness.
"""

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING

import redis.asyncio as redis_async

from app.core.exceptions import SupplierRateLimitedError

if TYPE_CHECKING:
    from redis.asyncio.client import Redis

# Capacity & elapsed-time refill, returns wait time in ms (0 if acquired).
# KEYS[1] = bucket key
# ARGV[1] = capacity (integer, tokens per minute)
# ARGV[2] = now_ms (integer, current Unix timestamp in milliseconds)
# Stored hash fields: tokens (float), last_refill_ms (integer)
_TOKEN_BUCKET_LUA = """
local key = KEYS[1]
local capacity = tonumber(ARGV[1])
local now_ms = tonumber(ARGV[2])
local refill_rate_per_ms = capacity / 60000.0

local data = redis.call('HMGET', key, 'tokens', 'last_refill_ms')
local tokens = tonumber(data[1])
local last_refill_ms = tonumber(data[2])

if tokens == nil or last_refill_ms == nil then
  tokens = capacity
  last_refill_ms = now_ms
else
  local elapsed_ms = now_ms - last_refill_ms
  if elapsed_ms > 0 then
    tokens = math.min(capacity, tokens + elapsed_ms * refill_rate_per_ms)
    last_refill_ms = now_ms
  end
end

local wait_ms = 0
if tokens >= 1 then
  tokens = tokens - 1
else
  wait_ms = math.ceil((1 - tokens) / refill_rate_per_ms)
end

redis.call('HSET', key, 'tokens', tokens, 'last_refill_ms', last_refill_ms)
redis.call('PEXPIRE', key, 120000)
return wait_ms
"""

_MAX_WAIT_MS = 60_000


_client: Redis[bytes] | None = None


def _get_client() -> Redis[bytes]:
    global _client
    if _client is None:
        from app.core.config import get_settings

        _client = redis_async.from_url(
            get_settings().celery_broker_url,
            decode_responses=True,
            # Production stability: detect dropped connections within 30s
            # (default would block indefinitely on a dead TCP socket).
            socket_keepalive=True,
            socket_connect_timeout=5,
            socket_timeout=5,
            health_check_interval=30,
            retry_on_timeout=True,
        )
    return _client


def _set_client(client: Redis[bytes] | None) -> None:
    """Test seam: inject a fakeredis client and reset between tests."""
    global _client
    _client = client


async def acquire(bucket: str, limit_per_minute: int) -> None:
    """Block until 1 token can be consumed from `bucket`.

    Raises `SupplierRateLimitedError` if the wait exceeds the per-call cap
    (60 seconds) — the caller should surface this as a typed `RATE_LIMITED`
    error rather than blocking forever.
    """

    if limit_per_minute <= 0:
        msg = f"limit_per_minute must be > 0, got {limit_per_minute}"
        raise ValueError(msg)

    client = _get_client()
    key = f"rate_limit:{bucket}"
    total_waited_ms = 0

    while True:
        now_ms = int(time.time() * 1000)
        wait_ms = int(
            await client.eval(  # type: ignore[no-untyped-call]
                _TOKEN_BUCKET_LUA,
                1,
                key,
                str(limit_per_minute),
                str(now_ms),
            )
        )
        if wait_ms == 0:
            return
        total_waited_ms += wait_ms
        if total_waited_ms > _MAX_WAIT_MS:
            raise SupplierRateLimitedError(
                f"rate_limit bucket={bucket} exhausted (waited {total_waited_ms}ms)",
            )
        await asyncio.sleep(wait_ms / 1000.0)
