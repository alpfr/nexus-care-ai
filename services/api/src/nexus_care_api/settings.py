"""Application settings.

All configuration comes from environment variables, validated by Pydantic.
Missing required settings fail at startup with a clear error rather than
crashing later when something tries to use them.
"""

from __future__ import annotations

import secrets
from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Settings for the clinical+AI API service."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="NEXUS_API_",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Environment ---
    environment: str = Field(
        default="development",
        description="One of: development, staging, production.",
    )

    # --- Database ---
    # In dev: postgresql+psycopg://nexus:nexus@localhost:5433/nexus_care
    # In prod: read from Google Secret Manager via External Secrets Operator.
    database_url: SecretStr = Field(
        default=SecretStr("postgresql+psycopg://nexus:nexus@localhost:5433/nexus_care"),
        description="Postgres DSN.",
    )

    # --- JWT signing ---
    # Default: a fresh random 256-bit key per process. Tokens become invalid
    # on restart, which is fine for dev. In prod, set NEXUS_API_JWT_SIGNING_KEY
    # explicitly from Google Secret Manager.
    jwt_signing_key: SecretStr = Field(
        default_factory=lambda: SecretStr(secrets.token_urlsafe(32)),
        description="HS256 signing key for JWTs.",
    )

    # --- Lockout policy ---
    failed_login_lock_threshold: int = 5
    lockout_minutes: int = 15

    # --- CORS (frontend origin) ---
    frontend_origin: str = "http://localhost:3000"

    # --- Misc ---
    log_level: str = "INFO"
    sql_echo: bool = False  # only flip to True for local SQL debugging


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached settings — read once per process."""
    return Settings()
