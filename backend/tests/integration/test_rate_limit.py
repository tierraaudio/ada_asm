"""Integration test for the rate limit on /auth/login.

We lower the per-minute limit via env, rebuild the app so the limiter sees
the new value, reset the limiter storage, and issue (limit + 1) requests.
The last MUST come back as 429 with a ``Retry-After`` header.
"""

from __future__ import annotations

from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

pytestmark = pytest.mark.integration


@pytest.fixture
def restricted_app(monkeypatch: pytest.MonkeyPatch) -> Any:
    monkeypatch.setenv("LOGIN_RATE_LIMIT_PER_MINUTE", "3")
    from app.api.v1.routers.auth import limiter
    from app.main import create_app

    limiter.reset()
    return create_app()


@pytest.fixture
async def restricted_client(restricted_app: Any):
    transport = ASGITransport(app=restricted_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


async def test_exceeding_login_rate_limit_returns_429(
    restricted_client: AsyncClient,
) -> None:
    # Three requests succeed at the validation layer (we don't care about
    # 401/200 here, only that the limiter has not been triggered).
    for _ in range(3):
        response = await restricted_client.post(
            "/api/v1/auth/login",
            json={"email": "no-one@nowhere.example", "password": "doesnt-matter-xx"},
        )
        assert response.status_code in {200, 401}

    # The 4th MUST be rate-limited.
    response = await restricted_client.post(
        "/api/v1/auth/login",
        json={"email": "no-one@nowhere.example", "password": "doesnt-matter-xx"},
    )
    assert response.status_code == 429
    assert response.json()["code"] == "RATE_LIMIT_EXCEEDED"
    assert response.headers.get("Retry-After") is not None
