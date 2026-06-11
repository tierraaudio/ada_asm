"""Shared factory for resilient async Redis clients.

Every async Redis consumer in the app (lookup cache, FX cache, rate
limiter) builds its client here so the connection-resilience policy
lives in exactly one place.

Why this policy exists: in Azure Container Apps the Redis instance is
reached through the environment's internal TCP ingress (Envoy), which
silently drops idle connections after a few minutes. A pooled socket
can therefore be dead without the client knowing. The settings below
make every command:

- detect dead sockets quickly (`socket_timeout` / `health_check_interval`),
- transparently reconnect-and-retry on `ConnectionError` — NOT only on
  `TimeoutError`, which is what the default `retry_on_timeout` covers —
  with a bounded exponential backoff (3 attempts, capped at 1s).

A command only fails after ~3s of retries, instead of either failing
instantly on the first dead socket or hanging for minutes.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import redis.asyncio as redis_async
from redis.asyncio.retry import Retry
from redis.backoff import ExponentialBackoff
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import TimeoutError as RedisTimeoutError

from app.core.config import get_settings

if TYPE_CHECKING:
    from redis.asyncio.client import Redis


def create_resilient_client() -> Redis[bytes]:
    """Build an async Redis client hardened for flaky internal ingress."""

    return redis_async.from_url(
        get_settings().celery_broker_url,
        decode_responses=True,
        socket_keepalive=True,
        socket_connect_timeout=10,
        socket_timeout=10,
        health_check_interval=30,
        retry=Retry(ExponentialBackoff(cap=1.0, base=0.1), retries=3),
        retry_on_error=[RedisConnectionError, RedisTimeoutError],
    )
