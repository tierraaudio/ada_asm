"""Unit tests for `app.infrastructure.observability`.

The whole point of this module is "do nothing when not configured,
wire OpenTelemetry when configured". These tests pin both paths.
"""

from __future__ import annotations

import pytest

from app.core.config import Settings
from app.infrastructure import observability


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


@pytest.fixture(autouse=True)
def _reset_observability_module_state() -> None:
    """`observability.init()` keeps a module-level idempotency flag.
    Each test starts from a clean slate so order doesn't matter."""
    observability._reset_for_tests()
    yield
    observability._reset_for_tests()


def test_init_is_noop_without_connection_string(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings(monkeypatch)
    assert settings.applicationinsights_connection_string is None
    result = observability.init(app=None, settings=settings)
    assert result is False
    assert observability.is_initialised() is False


def test_init_is_noop_with_empty_string(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings(monkeypatch, APPLICATIONINSIGHTS_CONNECTION_STRING="")
    result = observability.init(app=None, settings=settings)
    assert result is False


def test_environment_name_defaults_to_local(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings(monkeypatch)
    assert settings.environment_name == "local"


def test_environment_name_reads_from_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings(monkeypatch, ENVIRONMENT_NAME="prod")
    assert settings.environment_name == "prod"


def test_init_is_idempotent_with_connection_string(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When the connection string IS set, init() runs once and subsequent
    calls return True without re-registering exporters. Skipped when the
    optional Azure Monitor exporter is not installed (CI installs it from
    pyproject.toml; bare local venvs may not)."""

    pytest.importorskip("azure.monitor.opentelemetry.exporter")

    settings = _settings(
        monkeypatch,
        APPLICATIONINSIGHTS_CONNECTION_STRING=(
            "InstrumentationKey=00000000-0000-0000-0000-000000000000;"
            "IngestionEndpoint=https://westeurope-1.in.applicationinsights.azure.com/"
        ),
    )

    # Patch the Azure exporter so the test doesn't try to phone home.
    class _FakeExporter:
        def __init__(self, *_a: object, **_k: object) -> None:
            pass

        def export(self, *_a: object, **_k: object) -> int:
            return 0

        def shutdown(self) -> None:
            pass

    monkeypatch.setattr(
        "azure.monitor.opentelemetry.exporter.AzureMonitorTraceExporter",
        _FakeExporter,
    )

    first = observability.init(app=None, settings=settings)
    second = observability.init(app=None, settings=settings)
    assert first is True
    assert second is True
    assert observability.is_initialised() is True
