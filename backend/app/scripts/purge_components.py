"""Delete ALL components (and cascade-dependent rows) for a clean slate.

Used once before the ASM legacy migration so the catalogue is exactly what the
old ASM holds. Destructive — requires an explicit `--yes`. Runs in the backend
environment: `python -m app.scripts.purge_components --yes`.

`TRUNCATE ... CASCADE` also clears the rows that reference components
(supplier_prices/stocks, blended tables, child edges) — which is the intended
clean slate.
"""

from __future__ import annotations

import argparse
import asyncio

from sqlalchemy import text

from app.infrastructure.db.session import get_session_factory


async def _purge() -> int:
    factory = get_session_factory()
    async with factory() as session:
        before = (await session.execute(text("SELECT count(*) FROM components"))).scalar_one()
        await session.execute(text("TRUNCATE TABLE components CASCADE"))
        await session.commit()
        after = (await session.execute(text("SELECT count(*) FROM components"))).scalar_one()
    print(f"purge_components: deleted {before} components (now {after})")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Delete ALL components (clean slate).")
    p.add_argument("--yes", action="store_true", help="Required confirmation.")
    args = p.parse_args(argv)
    if not args.yes:
        print("Refusing: pass --yes to confirm deleting ALL components.")
        return 1
    return asyncio.run(_purge())


if __name__ == "__main__":
    raise SystemExit(main())
