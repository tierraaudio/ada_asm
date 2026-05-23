"""Integration-test fixtures.

Provides ``seeded_user`` and ``seeded_admin`` factory fixtures backed by the
running PostgreSQL container.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Literal

import pytest
from httpx import AsyncClient

from app.domain.entities.component import Component
from app.domain.entities.component_purchase import ComponentPurchase
from app.domain.entities.user import User
from app.infrastructure.db.session import get_session_factory
from app.infrastructure.repositories.component_purchase_repository import (
    SqlAlchemyComponentPurchaseRepository,
)
from app.infrastructure.repositories.component_repository import (
    SqlAlchemyComponentRepository,
)
from app.infrastructure.repositories.user_repository import SqlAlchemyUserRepository
from app.infrastructure.security import hash_password


async def _seed(
    *,
    email: str = "alice@example.com",
    password: str = "long-enough-passphrase",
    full_name: str = "Alice Test",
    role: Literal["admin", "user"] = "user",
    is_active: bool = True,
) -> User:
    factory = get_session_factory()
    async with factory() as session:
        repo = SqlAlchemyUserRepository(session)
        user = User(
            email=email,
            password_hash=hash_password(password),
            full_name=full_name,
            global_role=role,
            is_active=is_active,
        )
        saved = await repo.save(user)
        await session.commit()
        return saved


@pytest.fixture
async def seeded_user() -> User:
    return await _seed()


@pytest.fixture
async def seeded_admin() -> User:
    return await _seed(
        email="admin@example.com",
        password="admin-long-passphrase",
        full_name="Admin Test",
        role="admin",
    )


@pytest.fixture
async def seeded_inactive() -> User:
    return await _seed(
        email="ghost@example.com",
        password="ghost-long-passphrase",
        is_active=False,
    )


# ---------- Components helpers ----------


async def _login_for(api_client: AsyncClient, *, email: str, password: str) -> dict[str, str]:
    response = await api_client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    body = response.json()
    return {"Authorization": f"Bearer {body['access_token']}"}


@pytest.fixture
async def auth_headers(api_client: AsyncClient, seeded_user: User) -> dict[str, str]:
    """Bearer headers for the default ``seeded_user``."""
    return await _login_for(api_client, email=seeded_user.email, password="long-enough-passphrase")


def _make_component(
    *,
    mpn: str = "ACS712",
    sku: str | None = "ACS712-30A",
    name: str = "Sensor Hall",
    family: str = "Sensores",
    tier: str = "B",
    nato_score: str = "otan",
    supplier: str | None = "DigiKey",
    location: str | None = "A-1",
    description: str | None = "Sensor de corriente Hall",
    price_per_100: Decimal | None = Decimal("8.4500"),
    stock: int = 10,
    country_of_origin: str | None = "US",
    datasheet_url: str | None = None,
) -> Component:
    return Component(
        mpn=mpn,
        sku=sku,
        name=name,
        family=family,
        tier=tier,  # type: ignore[arg-type]
        nato_score=nato_score,  # type: ignore[arg-type]
        supplier=supplier,
        location=location,
        description=description,
        datasheet_url=datasheet_url,
        price_per_100=price_per_100,
        stock=stock,
        country_of_origin=country_of_origin,
    )


@pytest.fixture
async def seeded_component() -> Component:
    """Persist a single Component and return its hydrated form."""
    factory = get_session_factory()
    async with factory() as session:
        repo = SqlAlchemyComponentRepository(session)
        saved = await repo.save(_make_component())
        await session.commit()
        return saved


@pytest.fixture
async def seeded_components_catalogue() -> list[Component]:
    """Persist a small, deterministic catalogue used by list / filter tests."""
    samples = [
        _make_component(
            mpn="ACS712",
            sku="ACS712-30A",
            name="Sensor corriente Hall",
            family="Sensores",
            supplier="DigiKey",
            tier="B",
            nato_score="otan",
        ),
        _make_component(
            mpn="BME280",
            sku="BME280-ENV",
            name="Sensor ambiental T/H/P",
            family="Sensores",
            supplier="DigiKey",
            tier="B",
            nato_score="allied_otan",
        ),
        _make_component(
            mpn="ESP32-WROOM-32E",
            sku="ESP32-E",
            name="Modulo WiFi + Bluetooth",
            family="Microcontroladores",
            supplier="Mouser",
            tier="A",
            nato_score="high_risk",
        ),
        _make_component(
            mpn="STM32F407VGT6",
            sku="STM32F407",
            name="MCU ARM Cortex-M4",
            family="Microcontroladores",
            supplier="DigiKey",
            tier="A+",
            nato_score="allied_otan",
        ),
        _make_component(
            mpn="NE555",
            sku="NE555-DIP",
            name="Timer NE555",
            family="Discretos",
            supplier="Farnell",
            tier="D",
            nato_score="100_otan",
        ),
    ]
    factory = get_session_factory()
    saved: list[Component] = []
    async with factory() as session:
        repo = SqlAlchemyComponentRepository(session)
        for sample in samples:
            saved.append(await repo.save(sample))
        await session.commit()
    return saved


@pytest.fixture
async def seeded_component_with_purchases() -> Component:
    """Component plus three purchases on distinct dates (newest = today)."""
    factory = get_session_factory()
    today = date.today()
    async with factory() as session:
        component_repo = SqlAlchemyComponentRepository(session)
        purchase_repo = SqlAlchemyComponentPurchaseRepository(session)
        component = await component_repo.save(_make_component(mpn="BME280"))
        for days_ago, qty, unit in (
            (5, 100, Decimal("0.0480")),
            (30, 250, Decimal("0.0475")),
            (180, 500, Decimal("0.0490")),
        ):
            await purchase_repo.save(
                ComponentPurchase(
                    component_id=component.id,
                    purchased_at=today - timedelta(days=days_ago),
                    quantity=qty,
                    supplier="DigiKey",
                    unit_cost=unit,
                    total_cost=(unit * Decimal(qty)).quantize(Decimal("0.0001")),
                )
            )
        await session.commit()
        return component
