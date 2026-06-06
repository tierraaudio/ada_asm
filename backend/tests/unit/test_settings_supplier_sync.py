"""Unit tests for the supplier-sync settings block in `app.core.config`.

Covers defaults, comma-separated parsing, and the case-insensitivity of the
supplier code lists. The Settings class is built per-test via
`Settings(_env_file=None, **overrides)` so we don't depend on the ambient
environment.
"""

from __future__ import annotations

import pytest

from app.core.config import Settings

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


def test_supplier_sync_defaults_exclude_rs(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _settings(monkeypatch)
    assert settings.supplier_sync_enabled_suppliers == [
        "mouser",
        "digikey",
        "tme",
        "farnell",
    ]
    assert settings.supplier_lookup_priority == [
        "mouser",
        "digikey",
        "tme",
        "farnell",
        "rs",
    ]
    assert settings.supplier_lookup_cache_ttl_seconds == 900
    assert settings.supplier_sync_daily_hour_utc == 3


def test_supplier_sync_enabled_parses_comma_separated(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _settings(
        monkeypatch,
        SUPPLIER_SYNC_ENABLED_SUPPLIERS="mouser, digikey , rs",
    )
    assert settings.supplier_sync_enabled_suppliers == ["mouser", "digikey", "rs"]


def test_supplier_sync_enabled_lowercases_input(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _settings(
        monkeypatch,
        SUPPLIER_SYNC_ENABLED_SUPPLIERS="MOUSER,Digikey,TmE",
    )
    assert settings.supplier_sync_enabled_suppliers == ["mouser", "digikey", "tme"]


def test_supplier_sync_enabled_empty_string_yields_empty_list(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings(monkeypatch, SUPPLIER_SYNC_ENABLED_SUPPLIERS="")
    assert settings.supplier_sync_enabled_suppliers == []


def test_supplier_lookup_priority_round_trips_through_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings(
        monkeypatch,
        SUPPLIER_LOOKUP_PRIORITY="tme,mouser,farnell",
    )
    assert settings.supplier_lookup_priority == ["tme", "mouser", "farnell"]


def test_supplier_credentials_default_to_none(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _settings(monkeypatch)
    assert settings.mouser_api_key is None
    assert settings.digikey_client_id is None
    assert settings.digikey_client_secret is None
    assert settings.tme_token is None
    assert settings.tme_app_secret is None
    assert settings.farnell_api_key is None
    assert settings.rs_api_key is None


def test_farnell_store_id_has_default(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _settings(monkeypatch)
    assert settings.farnell_store_id == "uk.farnell.com"


def test_digikey_token_url_has_default(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _settings(monkeypatch)
    assert settings.digikey_oauth_token_url == "https://api.digikey.com/v1/oauth2/token"


def test_daily_hour_must_be_in_range(monkeypatch: pytest.MonkeyPatch) -> None:
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        _settings(monkeypatch, SUPPLIER_SYNC_DAILY_HOUR_UTC="24")


def test_supplier_credentials_populate_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _settings(
        monkeypatch,
        MOUSER_API_KEY="abc-123",
        DIGIKEY_CLIENT_ID="cid",
        DIGIKEY_CLIENT_SECRET="csec",
    )
    assert settings.mouser_api_key == "abc-123"
    assert settings.digikey_client_id == "cid"
    assert settings.digikey_client_secret == "csec"
