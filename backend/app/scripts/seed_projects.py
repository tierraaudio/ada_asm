"""Seed sample customers + projects + consumption stock_events (Figma 46:3).

Inserts:
- 3 customers (Holded-style ids).
- 5 projects covering all 4 statuses (Draft / Active / Delivered / Archived),
  one empty-BOM Draft and one Active mixing module + component direct children.
- A handful of `consumption` stock_events linking to the Active projects so
  the "Histórico de eventos" tab in the detail page has rows.

Usage:
    python -m app.scripts.seed_projects [--reset]

`--reset` deletes `project_children`, `projects`, and `customers` in that
order before re-seeding (component + module data is preserved).

Refuses with exit 2 if `projects` is non-empty without `--reset`.
Refuses with exit 3 if components or modules aren't seeded yet (this script
is a thin compose of the other two — they MUST run first).
"""

from __future__ import annotations

import argparse
import asyncio
import random
import sys
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.application.services.projects_service import (
    AddProjectChildInput,
    ProjectCreate,
    ProjectService,
)
from app.domain.entities.customer import Customer
from app.domain.entities.project import ProjectStatus
from app.domain.entities.project_interest_link import ProjectInterestLink
from app.domain.entities.stock_event import StockEvent
from app.infrastructure.db.models.component import ComponentModel
from app.infrastructure.db.models.module import ModuleModel
from app.infrastructure.db.session import get_session_factory
from app.infrastructure.repositories.customer_repository import (
    SqlAlchemyCustomerRepository,
)
from app.infrastructure.repositories.project_interest_link_repository import (
    SqlAlchemyProjectInterestLinkRepository,
)
from app.infrastructure.repositories.stock_event_repository import (
    SqlAlchemyStockEventRepository,
)


@dataclass
class _CustomerSeed:
    holded_id: str
    name: str
    holded_url: str | None = None


@dataclass
class _ProjectSeed:
    code: str
    name: str
    description: str
    status: ProjectStatus
    customer_slug: str  # references one of _CUSTOMERS keys
    icon: str
    color: str
    tags: list[str]
    version: str
    fecha_inicio: date | None
    fecha_entrega_estimada: date | None
    fecha_entrega_real: date | None
    # BOM: list of (kind, slug, quantity). kind in ('module', 'component').
    # The slugs reference SKUs (modules) or MPNs (components) seeded earlier.
    bom: list[tuple[str, str, int]]
    # Sub-entity rows {name, url} for the "Enlaces de interés" surface.
    interest_links: list[tuple[str, str]]


_CUSTOMERS: dict[str, _CustomerSeed] = {
    "acme": _CustomerSeed(holded_id="HLD-CUST-001", name="ACME Aerospace"),
    "defensa": _CustomerSeed(holded_id="HLD-CUST-002", name="Defensa Levante"),
    "internal": _CustomerSeed(
        holded_id="HLD-CUST-003",
        name="Tierra Audio Internal",
        holded_url="https://internal.example/contact/3",
    ),
}

_TODAY = date.today()


def _date(offset_days: int) -> date:
    return _TODAY + timedelta(days=offset_days)


_PROJECTS: list[_ProjectSeed] = [
    _ProjectSeed(
        code="PRY-2026-001",
        name="Sensor Ambiental — Piloto ACME",
        description="Lote de prueba sin BOM cerrada todavía.",
        status="Presupuestado",
        customer_slug="acme",
        icon="🌡️",
        color="#3b82f6",
        tags=["pilot", "sensor", "outdoor"],
        version="v0.1",
        fecha_inicio=_date(0),
        fecha_entrega_estimada=_date(60),
        fecha_entrega_real=None,
        bom=[],
        interest_links=[
            ("Brief técnico (Notion)", "https://notion.example/projects/pry-2026-001-brief"),
        ],
    ),
    _ProjectSeed(
        code="PRY-2026-002",
        name="DAQ Embarcado ACME",
        description="Adquisición de datos para banco de ensayos aeronáutico.",
        status="En proceso",
        customer_slug="acme",
        icon="📊",
        color="#10b981",
        tags=["DAQ", "aeronautics", "embedded"],
        version="v1.0",
        fecha_inicio=_date(-15),
        fecha_entrega_estimada=_date(45),
        fecha_entrega_real=None,
        bom=[
            ("module", "MOD-DAQ-001", 1),
            ("module", "MOD-SENS-001", 2),
            ("component", "STM32F407VGT6", 5),
        ],
        interest_links=[
            ("Datasheet STM32F407", "https://www.st.com/resource/en/datasheet/stm32f407vg.pdf"),
            ("Especificación cliente", "https://acme.example/specs/daq-2026"),
        ],
    ),
    _ProjectSeed(
        code="PRY-2026-003",
        name="Sistema Potencia BLDC para Drones Defensa",
        description="Lote inicial: 4 dron-stations con potencia + sensores ambientales.",
        status="En proceso",
        customer_slug="defensa",
        icon="⚡",
        color="#ec4899",
        tags=["power", "motor", "automotive", "alta-corriente"],
        version="v2.1",
        fecha_inicio=_date(-30),
        fecha_entrega_estimada=_date(30),
        fecha_entrega_real=None,
        bom=[
            ("module", "MOD-DRONE-001", 4),
            ("component", "BME280", 8),
            ("component", "B340A", 16),
        ],
        interest_links=[
            ("Datasheet Motor", "https://docs.example.com/motor-bldc"),
            ("Plan de pruebas", "https://defensa.example/qa/plan-2026"),
            ("Esquema eléctrico (KiCad)", "https://kicad.example/sch/bldc-2026.pdf"),
        ],
    ),
    _ProjectSeed(
        code="PRY-2026-004",
        name="Estación Meteorológica Interna",
        description="Equipo de oficinas — entregado al equipo interno.",
        status="Completado",
        customer_slug="internal",
        icon="☀️",
        color="#f59e0b",
        tags=["weather", "internal"],
        version="v1.5",
        fecha_inicio=_date(-90),
        fecha_entrega_estimada=_date(-10),
        fecha_entrega_real=_date(-5),
        bom=[
            ("module", "MOD-STATION-001", 1),
        ],
        interest_links=[],
    ),
    _ProjectSeed(
        code="PRY-2025-099",
        name="Proyecto Archivado Antiguo",
        description="Proyecto retirado — se conserva para histórico.",
        status="Archivado",
        customer_slug="defensa",
        icon="📦",
        color="#71717a",
        tags=["legacy"],
        version="v0.9",
        fecha_inicio=_date(-365),
        fecha_entrega_estimada=_date(-300),
        fecha_entrega_real=None,
        bom=[
            ("component", "STM32F407VGT6", 2),
        ],
        interest_links=[],
    ),
]


async def _ensure_prereqs(
    session_factory: async_sessionmaker[AsyncSession],
) -> tuple[dict[str, UUID], dict[str, UUID]]:
    """Pull component MPN→id and module SKU→id maps. Exits 3 if either is empty."""
    async with session_factory() as session:
        comp_rows = (
            await session.execute(select(ComponentModel.id, ComponentModel.mpn))
        ).all()
        mod_rows = (await session.execute(select(ModuleModel.id, ModuleModel.sku))).all()

    if not comp_rows or not mod_rows:
        print(
            "seed_projects: components or modules are not seeded yet.\n"
            "Run `python -m app.scripts.seed_components` and "
            "`python -m app.scripts.seed_modules` first.",
            file=sys.stderr,
        )
        sys.exit(3)

    by_mpn: dict[str, UUID] = {row[1]: row[0] for row in comp_rows}
    by_sku: dict[str, UUID] = {row[1]: row[0] for row in mod_rows}
    return by_mpn, by_sku


async def _reset(session_factory: async_sessionmaker[AsyncSession]) -> None:
    """Wipe project + customer data, leaving modules + components untouched."""
    async with session_factory() as session:
        await session.execute(
            text("DELETE FROM stock_events WHERE project_id IS NOT NULL")
        )
        await session.execute(text("DELETE FROM project_children"))
        await session.execute(text("DELETE FROM projects"))
        await session.execute(text("DELETE FROM customers"))
        await session.commit()


async def _has_projects(session_factory: async_sessionmaker[AsyncSession]) -> bool:
    async with session_factory() as session:
        row = (await session.execute(text("SELECT 1 FROM projects LIMIT 1"))).first()
        return row is not None


async def seed(reset: bool = False) -> None:
    session_factory = get_session_factory()
    if reset:
        await _reset(session_factory)
    elif await _has_projects(session_factory):
        print(
            "seed_projects: `projects` is non-empty. Pass --reset to wipe + re-seed.",
            file=sys.stderr,
        )
        sys.exit(2)

    by_mpn, by_sku = await _ensure_prereqs(session_factory)

    # ----- customers -----
    customer_ids: dict[str, UUID] = {}
    async with session_factory() as session:
        repo = SqlAlchemyCustomerRepository(session)
        for slug, seed_row in _CUSTOMERS.items():
            saved = await repo.save(
                Customer(
                    holded_id=seed_row.holded_id,
                    name=seed_row.name,
                    holded_url=seed_row.holded_url,
                )
            )
            customer_ids[slug] = saved.id

    # ----- projects + BOM + interest_links -----
    project_ids: dict[str, UUID] = {}
    interest_links_seeded = 0
    async with session_factory() as session:
        svc = ProjectService(session)
        links_repo = SqlAlchemyProjectInterestLinkRepository(session)
        for p in _PROJECTS:
            created = await svc.create(
                ProjectCreate(
                    code=p.code,
                    name=p.name,
                    description=p.description,
                    status=p.status,
                    customer_id=customer_ids[p.customer_slug],
                    icon=p.icon,
                    color=p.color,
                    tags=list(p.tags),
                    version=p.version,
                    fecha_inicio=p.fecha_inicio,
                    fecha_entrega_estimada=p.fecha_entrega_estimada,
                    fecha_entrega_real=p.fecha_entrega_real,
                )
            )
            project_ids[p.code] = created.id
            for idx, (link_name, link_url) in enumerate(p.interest_links):
                await links_repo.save(
                    ProjectInterestLink(
                        project_id=created.id,
                        name=link_name,
                        url=link_url,
                        sort_order=idx,
                    )
                )
                interest_links_seeded += 1
            for kind, slug, qty in p.bom:
                if kind == "module":
                    child_module_id = by_sku.get(slug)
                    if child_module_id is None:
                        print(
                            f"seed_projects: module {slug!r} not found — skipping.",
                            file=sys.stderr,
                        )
                        continue
                    await svc.add_child(
                        created.id,
                        AddProjectChildInput(
                            child_module_id=child_module_id, quantity=qty
                        ),
                    )
                else:
                    child_component_id = by_mpn.get(slug)
                    if child_component_id is None:
                        print(
                            f"seed_projects: component {slug!r} not found — skipping.",
                            file=sys.stderr,
                        )
                        continue
                    await svc.add_child(
                        created.id,
                        AddProjectChildInput(
                            child_component_id=child_component_id, quantity=qty
                        ),
                    )

    # ----- consumption stock_events tied to a couple of Active projects -----
    rng = random.Random(42)
    consumed = 0
    async with session_factory() as session:
        events_repo = SqlAlchemyStockEventRepository(session)
        # Allocate consumption from STM32 to PRY-2026-002 (4 events) and from
        # BME280 to PRY-2026-003 (2 events).
        consumption_plan: list[tuple[str, str, int]] = [
            ("STM32F407VGT6", "PRY-2026-002", 1),
            ("STM32F407VGT6", "PRY-2026-002", 2),
            ("STM32F407VGT6", "PRY-2026-002", 1),
            ("STM32F407VGT6", "PRY-2026-002", 1),
            ("BME280", "PRY-2026-003", 2),
            ("BME280", "PRY-2026-003", 1),
        ]
        for mpn, code, qty in consumption_plan:
            component_id = by_mpn.get(mpn)
            project_id = project_ids.get(code)
            if component_id is None or project_id is None:
                continue
            await events_repo.save(
                StockEvent(
                    component_id=component_id,
                    module_id=None,
                    kind="consumption",
                    quantity=qty,
                    occurred_at=_date(-rng.randint(1, 20)),
                    notes=None,
                    supplier_id=None,
                    unit_cost=None,
                    total_cost=None,
                    currency="EUR",
                    project_id=project_id,
                    project_name_snapshot=next(
                        p.name for p in _PROJECTS if p.code == code
                    ),
                    customer_id_holded=None,
                    customer_name_snapshot=None,
                )
            )
            consumed += 1
        await session.commit()

    print(
        f"Seeded {len(customer_ids)} customers + {len(project_ids)} projects "
        f"+ {interest_links_seeded} interest links "
        f"+ {consumed} consumption stock_events.",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed projects + customers.")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Delete project_children, projects, and customers before re-seeding.",
    )
    args = parser.parse_args()
    asyncio.run(seed(reset=args.reset))


if __name__ == "__main__":
    main()


# `Decimal` is unused but imported keeping parity with sibling seed scripts;
# the linter accepts the symbol via the explicit re-export below.
_ = Decimal
