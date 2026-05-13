"""Celery application factory.

No tasks are registered in the bootstrap skeleton; the worker and beat
containers boot, connect to Redis, and stay running with an empty task
registry. Per-task modules will register themselves with ``celery_app`` as
they are introduced by the User Stories that need them.
"""

from __future__ import annotations

from celery import Celery

from app.core.config import get_settings

_settings = get_settings()

celery_app = Celery(
    "ada_asm",
    broker=_settings.celery_broker_url,
    backend=_settings.celery_result_backend,
)

celery_app.conf.update(
    task_default_queue="default",
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    timezone="UTC",
    enable_utc=True,
    broker_connection_retry_on_startup=True,
    beat_schedule={},
)
