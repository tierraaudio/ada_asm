"""Unit tests for the supplier registry.

Concrete adapters don't exist yet at this checkpoint — we patch the
adapter factory so the registry's iteration logic can be tested in
isolation from the HTTP-level adapter code.
"""

from __future__ import annotations

import pytest

from app.core.config import Settings
from app.infrastructure.suppliers import registry


_BASE_ENV: dict[str, str] = {
    "DATABASE_URL": "postgresql+asyncpg://x:y@db:5432/z",
    "CELERY_BROKER_URL": "redis://r:6379/0",
    "CELERY_RESULT_BACKEND": "redis://r:6379/1",
    "JWT_SECRET": "test-secret-12345678",
}


def _settings(monkeypatch: pytest.MonkeyPatch, **overrides: str) -> Settings:
    for key, value in {**_BASE_ENV, **overrides}.items():
        monkeypatch.setenv(key, value)
    return Settings()


def test_has_credentials_per_supplier(monkeypatch: pytest.MonkeyPatch) -> None:
    s = _settings(
        monkeypatch,
        MOUSER_API_KEY="m-key",
        DIGIKEY_CLIENT_ID="d-id",
        DIGIKEY_CLIENT_SECRET="d-sec",
        TME_TOKEN="t-token",
        TME_APP_SECRET="t-sec",
        FARNELL_API_KEY="f-key",
        # RS intentionally absent
    )
    assert registry._has_credentials("mouser", s) is True
    assert registry._has_credentials("digikey", s) is True
    assert registry._has_credentials("tme", s) is True
    assert registry._has_credentials("farnell", s) is True
    assert registry._has_credentials("rs", s) is False


def test_has_credentials_requires_both_digikey_pieces(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    s = _settings(monkeypatch, DIGIKEY_CLIENT_ID="only-id")
    assert registry._has_credentials("digikey", s) is False


def test_has_credentials_requires_both_tme_pieces(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    s = _settings(monkeypatch, TME_TOKEN="only-token")
    assert registry._has_credentials("tme", s) is False


def test_enabled_adapters_skips_missing_creds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    s = _settings(
        monkeypatch,
        SUPPLIER_SYNC_ENABLED_SUPPLIERS="mouser,rs",
        MOUSER_API_KEY="m-key",
        # RS_API_KEY absent → registry must skip RS silently.
    )

    built: list[str] = []

    def fake_build(code: str, _settings: Settings) -> object:
        built.append(code)
        return object()  # opaque placeholder; registry doesn't introspect

    monkeypatch.setattr(registry, "_build_adapter", fake_build)
    out = registry.enabled_adapters(settings=s)
    assert built == ["mouser"]
    assert len(out) == 1


def test_enabled_adapters_skips_codes_disabled_by_flag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    s = _settings(
        monkeypatch,
        SUPPLIER_SYNC_ENABLED_SUPPLIERS="digikey,tme",
        MOUSER_API_KEY="m-key",  # configured but DISABLED → must be skipped
        DIGIKEY_CLIENT_ID="d-id",
        DIGIKEY_CLIENT_SECRET="d-sec",
        TME_TOKEN="t-token",
        TME_APP_SECRET="t-sec",
    )

    built: list[str] = []

    def fake_build(code: str, _settings: Settings) -> object:
        built.append(code)
        return object()

    monkeypatch.setattr(registry, "_build_adapter", fake_build)
    registry.enabled_adapters(settings=s)
    assert built == ["digikey", "tme"]
    assert "mouser" not in built


def test_lookup_adapters_obey_priority_order_and_enabled_intersection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    s = _settings(
        monkeypatch,
        SUPPLIER_SYNC_ENABLED_SUPPLIERS="mouser,tme",
        SUPPLIER_LOOKUP_PRIORITY="rs,tme,mouser,digikey",  # rs+digikey absent
        MOUSER_API_KEY="m-key",
        TME_TOKEN="t-token",
        TME_APP_SECRET="t-sec",
    )

    built: list[str] = []

    def fake_build(code: str, _settings: Settings) -> object:
        built.append(code)
        return object()

    monkeypatch.setattr(registry, "_build_adapter", fake_build)
    registry.lookup_adapters_in_priority_order(settings=s)
    # Priority order is preserved; rs (not enabled) and digikey (not enabled)
    # are filtered out before construction.
    assert built == ["tme", "mouser"]


def test_enabled_adapters_returns_empty_when_all_skipped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    s = _settings(
        monkeypatch,
        SUPPLIER_SYNC_ENABLED_SUPPLIERS="rs",
        # RS_API_KEY absent → silent skip.
    )
    monkeypatch.setattr(registry, "_build_adapter", lambda *_a, **_k: object())
    assert registry.enabled_adapters(settings=s) == []
