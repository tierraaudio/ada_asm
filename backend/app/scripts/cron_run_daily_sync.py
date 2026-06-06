"""KEDA cron entry-point for the daily supplier sync.

Invoked by the `caj-ada-asm-beat-cron-<env>` Container App Job at
03:00 UTC (configurable via `SUPPLIER_SYNC_DAILY_HOUR_UTC`). Replaces
the long-running `celery_beat` container — the orchestrator now starts
on schedule, runs `run_daily_sync()` synchronously, and exits.

The job exits 0 on success (whether or not individual suppliers had
errors — those are captured in `supplier_sync_errors` and reflected in
each run row's `status`). Exits non-zero only on uncaught Python
exceptions; the KEDA controller will retry once per `replicaRetryLimit`.

Logs route to Container Apps' stdout sink → Log Analytics, with the
active OTel `trace_id` correlated back to App Insights.
"""

from __future__ import annotations

import logging
import sys

from app.infrastructure import observability
from app.infrastructure.tasks.supplier_sync import run_daily_sync

_log = logging.getLogger(__name__)


def main() -> int:
    # Wire telemetry first so the orchestrator's traces are captured.
    observability.init(app=None)

    _log.info("cron_run_daily_sync: starting")
    try:
        # `run_daily_sync` is a Celery task wrapping a sync function.
        # Calling it directly (NOT via `.delay()`) runs the orchestration
        # in THIS process — it enqueues one `sync_one_supplier` sub-task
        # per enabled supplier and returns the list of (supplier, task_id)
        # pairs. The actual per-supplier work happens in the workers; we
        # exit after enqueuing.
        enqueued = run_daily_sync()
        _log.info(
            "cron_run_daily_sync: completed enqueued=%s",
            enqueued,
        )
        return 0
    except Exception:
        _log.exception("cron_run_daily_sync: failed with uncaught exception")
        return 2


if __name__ == "__main__":
    sys.exit(main())
