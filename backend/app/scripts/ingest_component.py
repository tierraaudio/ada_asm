"""CLI to ingest a component from a manufacturer MPN.

Usage:
    python -m app.scripts.ingest_component <MPN> [--ubicacion ...]
        [--stock-inicial N] [--holded-id ...] [--force]

Runnable locally via `docker exec` and in production as a one-off Container
App Job. Shares the same `ComponentIngestionService` as the HTTP endpoint;
prints a human-readable rendering of the ingestion report. Exits 0 on
success, non-zero on a typed error. See change `ingest-component-from-mpn`.
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from app.application.services.component_ingestion_service import (
    ComponentIngestionService,
    IngestionReport,
)
from app.core.exceptions import DomainError
from app.infrastructure.datasheet_storage import get_datasheet_storage
from app.infrastructure.db.session import get_session_factory


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Ingest a component from its manufacturer MPN."
    )
    parser.add_argument("mpn", help="Manufacturer part number, e.g. NE555P")
    parser.add_argument("--ubicacion", default=None)
    parser.add_argument("--stock-inicial", type=int, default=None)
    parser.add_argument("--holded-id", default=None)
    parser.add_argument("--force", action="store_true")
    return parser


def _render_report(report: IngestionReport, component_id: str) -> str:
    fam = report.family
    ds = report.datasheet
    lines = [
        f"Ingested {report.mpn} → {component_id}",
        f"  SKU: {report.sku}",
        f"  Status: {report.status}",
        f"  Suppliers: consulted={report.sources_consulted} "
        f"succeeded={report.sources_succeeded} contributed={report.sources_contributed}",
        f"  Family: {fam['inferred'] or '(needs review)'} "
        f"(by {fam['decided_by']} via {fam['match_type']}, conf={fam['confidence']})",
        f"  Datasheet: {ds['outcome']} source={ds['source']} blob={ds['blob_path']}",
        f"  Counts: {report.counts}",
        f"  Fields populated: {report.fields_populated}",
        f"  Manual overrides: {report.manual_overrides_applied}",
    ]
    if report.warnings:
        lines.append(f"  Warnings: {report.warnings}")
    return "\n".join(lines)


async def _ingest(args: argparse.Namespace) -> int:
    factory = get_session_factory()
    async with factory() as session:
        service = ComponentIngestionService(session, storage=get_datasheet_storage())
        component, report = await service.ingest(
            args.mpn,
            ubicacion=args.ubicacion,
            stock_inicial=args.stock_inicial,
            holded_id=args.holded_id,
            force=args.force,
        )
    print(_render_report(report, str(component.id)))
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        return asyncio.run(_ingest(args))
    except DomainError as exc:
        print(f"ERROR {exc.code}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
