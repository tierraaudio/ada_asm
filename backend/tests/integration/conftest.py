"""Integration-test fixtures.

Provides ``seeded_user`` / ``seeded_admin`` / ``seeded_inactive`` users plus
``auth_headers`` (bearer for the default user) and a small catalogue of
seeded components for the list-page tests.
"""

from __future__ import annotations

from typing import Literal

import pytest
from httpx import AsyncClient

from app.domain.entities.component import Component, NatoScoreValue, TierValue
from app.domain.entities.supplier import Supplier
from app.domain.entities.user import User
from app.infrastructure.db.session import get_session_factory
from app.infrastructure.repositories.component_repository import (
    SqlAlchemyComponentRepository,
)
from app.infrastructure.repositories.supplier_repository import (
    SqlAlchemySupplierRepository,
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
    mpn: str = "STM32F407VGT6",
    sku: str | None = "MCU-001",
    name: str = "STM32F407VGT6 - ARM Cortex-M4 MCU",
    family: str = "Microcontroladores",
    tier: TierValue = 1,
    nato_score: NatoScoreValue = "A+",
    location: str | None = "G-A-12",
    fabricante: str | None = "STMicroelectronics",
    tipo_almacenamiento: str | None = "Gaveta",
    description: str | None = "MCU 32-bit",
    stock: int = 145,
    stock_min: int | None = 5,
    country_of_origin: str | None = "FR",
    datasheet_url: str | None = None,
    proveedor_preferente_id: object | None = None,
) -> Component:
    return Component(
        mpn=mpn,
        sku=sku,
        name=name,
        family=family,
        tier=tier,
        nato_score=nato_score,
        location=location,
        fabricante=fabricante,
        tipo_almacenamiento=tipo_almacenamiento,
        description=description,
        datasheet_url=datasheet_url,
        stock=stock,
        stock_min=stock_min,
        country_of_origin=country_of_origin,
        proveedor_preferente_id=proveedor_preferente_id,  # type: ignore[arg-type]
    )


@pytest.fixture
async def seeded_component() -> Component:
    """Persist a single Component (no FK to suppliers — keeps the test scope tight)."""
    factory = get_session_factory()
    async with factory() as session:
        repo = SqlAlchemyComponentRepository(session)
        saved = await repo.save(_make_component())
        await session.commit()
        return saved


@pytest.fixture
async def seeded_suppliers() -> dict[str, Supplier]:
    factory = get_session_factory()
    async with factory() as session:
        repo = SqlAlchemySupplierRepository(session)
        suppliers = {}
        for name in ("DigiKey", "Mouser", "Farnell", "RS", "TME"):
            suppliers[name] = await repo.save(Supplier(name=name))
        await session.commit()
        return suppliers


@pytest.fixture
async def seeded_components_catalogue(
    seeded_suppliers: dict[str, Supplier],
) -> list[Component]:
    """A deterministic 5-component catalogue used by list / filter tests."""
    samples = [
        _make_component(
            mpn="STM32F407VGT6",
            sku="MCU-001",
            name="STM32F407VGT6 - ARM Cortex-M4 MCU",
            family="Microcontroladores",
            tier=1,
            nato_score="A+",
            proveedor_preferente_id=seeded_suppliers["DigiKey"].id,
        ),
        _make_component(
            mpn="BME280",
            sku="SEN-008",
            name="BME280 - Sensor ambiental digital",
            family="Sensores",
            tier=2,
            nato_score="A",
            proveedor_preferente_id=seeded_suppliers["Mouser"].id,
        ),
        _make_component(
            mpn="ESP32-WROOM-32",
            sku="MOD-053",
            name="ESP32-WROOM-32 - Módulo WiFi+BT",
            family="Módulos",
            tier=1,
            nato_score="D",
            proveedor_preferente_id=seeded_suppliers["TME"].id,
        ),
        _make_component(
            mpn="RC0805FR-0710K",
            sku="RES-112",
            name="Resistencia 10 kΩ 0805 1%",
            family="Resistencias",
            tier=3,
            nato_score="A+",
            proveedor_preferente_id=seeded_suppliers["TME"].id,
        ),
        _make_component(
            mpn="NE555",
            sku="IC-125",
            name="NE555 - Timer SOIC-8",
            family="Microcontroladores",
            tier=1,
            nato_score="A+",
            proveedor_preferente_id=seeded_suppliers["TME"].id,
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
