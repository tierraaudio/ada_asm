"""ENV-driven entry point for the ASM migration as a Container App Job.

Exposed as the console script ``asm-migrate`` so the job command is a single
dash-free token (``--command "asm-migrate"``) — avoiding the az CLI
``--command`` argparse limitation with dashed arguments. All config comes from
environment variables (set per run via ``job start --env-vars``):

  ASM_MODE       migrate (default) | purge
  ASM_ONLY       all (default) | distributor | internal
  ASM_LIMIT      int, 0 = all (default 0)
  ASM_OFFSET     int (default 0)
  ASM_DRY        "1" to dry-run
  ASM_PURGE_YES  "1" required when ASM_MODE=purge
"""

from __future__ import annotations

import argparse
import asyncio
import os

from app.scripts.migrate_asm import _run
from app.scripts.purge_components import _purge


def main() -> int:
    mode = os.environ.get("ASM_MODE", "migrate").lower()
    if mode == "purge":
        if os.environ.get("ASM_PURGE_YES") != "1":
            print("purge requires ASM_PURGE_YES=1")
            return 1
        return asyncio.run(_purge())

    ns = argparse.Namespace(
        offset=int(os.environ.get("ASM_OFFSET") or "0"),
        limit=int(os.environ.get("ASM_LIMIT") or "0"),
        only=os.environ.get("ASM_ONLY", "all"),
        dry_run=os.environ.get("ASM_DRY") == "1",
    )
    return asyncio.run(_run(ns))


if __name__ == "__main__":
    raise SystemExit(main())
