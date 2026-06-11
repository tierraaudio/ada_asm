"""Celery application factory.

Tasks register themselves with ``celery_app`` via the ``imports``
configuration below. The Beat schedule is the single place where
periodic invocations are declared.
"""

from __future__ import annotations

from celery import Celery
from celery.schedules import crontab

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
    # Production stability: prevent silent TCP drops on the broker
    # connection (CAE internal traffic). Cap retry/connect timeouts so
    # the producer (web backend) doesn't block the FastAPI event loop
    # for minutes when redis times out.
    broker_transport_options={
        "socket_keepalive": True,
        "socket_keepalive_options": {},
        "health_check_interval": 30,
        "max_retries": 3,
    },
    broker_connection_timeout=5,
    broker_connection_retry=True,
    broker_connection_max_retries=3,
    broker_pool_limit=10,
    # Modules whose `@celery_app.task` decorations register tasks on the
    # registry. Workers + beat need to import these on boot or the
    # registry is empty and tasks fail with KeyError.
    imports=("app.infrastructure.tasks.supplier_sync",),
    beat_schedule={
        # Daily supplier sync at the configured UTC hour. Enqueues one
        # `sync_one_supplier` task per enabled supplier so they run in
        # parallel on the worker pool.
        "supplier-sync-daily": {
            "task": "supplier_sync.run_daily_sync",
            "schedule": crontab(
                hour=str(_settings.supplier_sync_daily_hour_utc),
                minute="0",
            ),
        },
    },
)
