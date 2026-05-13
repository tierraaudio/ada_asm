"""Application settings loaded from environment variables.

The service refuses to boot if any required variable is missing — Pydantic's
ValidationError surfaces the missing field name before the ASGI server binds
to its port.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    """Strongly-typed application configuration."""

    model_config = SettingsConfigDict(
        env_file=None,
        case_sensitive=False,
        extra="ignore",
    )

    env: Literal["development", "staging", "production"] = Field(default="development")
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(default="INFO")
    app_version: str = Field(default="0.1.0")

    database_url: str = Field(..., description="SQLAlchemy URL, e.g. postgresql+asyncpg://...")
    celery_broker_url: str = Field(..., description="Redis URL for the Celery broker")
    celery_result_backend: str = Field(..., description="Redis URL for Celery results")

    jwt_secret: str = Field(..., min_length=8, description="Secret used to sign JWTs")
    jwt_access_token_ttl_seconds: int = Field(default=900)
    jwt_refresh_token_ttl_seconds: int = Field(default=14 * 24 * 3600)

    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=list,
        description="Comma-separated list of allowed CORS origins",
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_cors_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value


def get_settings() -> Settings:
    """Build the Settings instance from the current environment.

    Wrapped in a function (instead of a module-level singleton) so tests can
    monkeypatch environment variables and rebuild a fresh Settings without
    leakage between cases.
    """
    return Settings()
