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
    celery_broker_url: str = Field(
        ...,
        description=(
            "Celery broker URL. redis:// locally; azurestoragequeues:// in "
            "Azure (the CAE internal TCP ingress proved too unreliable to "
            "carry the broker — see change cloud-deployment-azure)"
        ),
    )
    celery_result_backend: str = Field(
        default="",
        description=(
            "UNUSED — kept for env compatibility. Task state lives in the "
            "supplier_sync_runs table; Celery results are ignored"
        ),
    )
    redis_cache_url: str = Field(
        default="",
        description=(
            "Redis URL for the app caches (lookup, FX, rate limiting). "
            "Falls back to celery_broker_url when empty (local dev, where "
            "the broker IS Redis). All cache consumers fail open, so an "
            "unreachable Redis degrades performance, never availability"
        ),
    )
    datasheet_storage_account_url: str = Field(
        default="",
        description=(
            "Azure Blob account URL (e.g. https://<acct>.blob.core.windows.net) "
            "for archived datasheets. Empty → filesystem driver (local/dev)."
        ),
    )
    datasheet_container: str = Field(default="datasheets")
    datasheet_local_root: str = Field(
        default="/tmp/ada_asm_datasheets",
        description="Filesystem root used when no Azure storage account is set.",
    )

    jwt_secret: str = Field(..., min_length=8, description="Secret used to sign JWTs")
    jwt_access_token_ttl_seconds: int = Field(default=900)
    jwt_refresh_token_ttl_seconds: int = Field(default=14 * 24 * 3600)
    password_reset_token_ttl_seconds: int = Field(default=3600)
    login_rate_limit_per_minute: int = Field(default=10)
    password_min_length: int = Field(default=12)
    password_max_length: int = Field(default=128)

    frontend_base_url: str = Field(
        default="http://localhost:5173",
        description="Base URL of the frontend, used to build password-reset links",
    )

    holded_base_url: str = Field(
        default="https://app.holded.com",
        description=(
            "Base URL of the Holded app. The customer link on the Project entity "
            "builds `${holded_base_url}/contact/{holded_id}` unless the Customer "
            "row provides an explicit `holded_url` override."
        ),
    )

    # ---- Cloud observability (change `cloud-deployment-azure`) ----
    #
    # When set, `app/infrastructure/observability.py::init()` wires the
    # OpenTelemetry SDK with the Azure Monitor exporter. When absent,
    # init() is a no-op so local dev is unchanged.
    applicationinsights_connection_string: str | None = Field(default=None)

    # Used as the `service.environment` resource attribute on every span
    # so App Insights can split metrics by environment without a custom
    # dimension on each emit.
    environment_name: str = Field(default="local")

    smtp_host: str | None = Field(default=None)
    smtp_port: int = Field(default=587)
    smtp_username: str | None = Field(default=None)
    smtp_password: str | None = Field(default=None)
    smtp_from: str | None = Field(default=None)
    smtp_use_tls: bool = Field(default=True)

    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=list,
        description="Comma-separated list of allowed CORS origins",
    )

    # ---- Supplier integration (change `supplier-sync`) ----
    #
    # Each supplier ships disabled until BOTH (a) its credentials are present
    # AND (b) its code is listed in `supplier_sync_enabled_suppliers`. The
    # registry layer (`app/infrastructure/suppliers/registry.py`) is the
    # single place that enforces this gate.
    mouser_api_key: str | None = Field(default=None)

    digikey_client_id: str | None = Field(default=None)
    digikey_client_secret: str | None = Field(default=None)
    digikey_oauth_token_url: str = Field(
        default="https://api.digikey.com/v1/oauth2/token",
    )

    tme_token: str | None = Field(default=None)
    tme_app_secret: str | None = Field(default=None)

    farnell_api_key: str | None = Field(default=None)
    farnell_store_id: str = Field(default="uk.farnell.com")

    rs_api_key: str | None = Field(default=None)

    supplier_sync_enabled_suppliers: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["mouser", "digikey", "tme", "farnell"],
        description=(
            "Comma-separated supplier codes that may be queried. "
            "RS Online is excluded by default until its App ID arrives."
        ),
    )
    supplier_lookup_priority: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["mouser", "digikey", "tme", "farnell", "rs"],
        description=(
            "Order in which the `/components/lookup` endpoint walks suppliers. "
            "Higher priority suppliers win on overlapping fields during the merge."
        ),
    )
    supplier_lookup_cache_ttl_seconds: int = Field(default=900)
    supplier_sync_daily_hour_utc: int = Field(default=3, ge=0, le=23)
    supplier_sync_daily_component_budget: int = Field(
        default=900,
        ge=0,
        description=(
            "Max components a quota-limited supplier syncs per day. DigiKey and "
            "Farnell cap the standard tier at 1000 requests/day (1 request per "
            "component), so the ~1840-component catalogue is split into "
            "ceil(total / budget) rotating packages, one advanced per calendar "
            "day. 0 disables rotation (sync the whole catalogue every day)."
        ),
    )
    supplier_sync_rotation_suppliers: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["mouser", "digikey", "farnell"],
        description=(
            "Supplier codes subject to the daily rotation budget. TME is "
            "excluded because it has no daily quota (per-minute limit only)."
        ),
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_cors_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @field_validator(
        "supplier_sync_enabled_suppliers",
        "supplier_lookup_priority",
        "supplier_sync_rotation_suppliers",
        mode="before",
    )
    @classmethod
    def _split_supplier_list(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip().lower() for item in value.split(",") if item.strip()]
        return value


def get_settings() -> Settings:
    """Build the Settings instance from the current environment.

    Wrapped in a function (instead of a module-level singleton) so tests can
    monkeypatch environment variables and rebuild a fresh Settings without
    leakage between cases.
    """
    return Settings()
