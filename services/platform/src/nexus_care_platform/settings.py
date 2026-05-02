"""Platform service settings.

Uses NEXUS_PLATFORM_-prefixed env vars (separate from NEXUS_API_) so the
two services can have different signing keys, log levels, etc., while
running side-by-side.
"""

from __future__ import annotations

import secrets
from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="NEXUS_PLATFORM_",
        case_sensitive=False,
        extra="ignore",
    )

    environment: str = "development"

    # In dev, identical to the API's DB. In production both services share
    # one Postgres instance but with role-scoped grants on the schemas.
    database_url: SecretStr = Field(
        default=SecretStr("postgresql+psycopg://nexus:nexus@localhost:5433/nexus_care"),
    )

    # Platform-admin JWT signing key. DELIBERATELY DIFFERENT from the
    # clinical API's signing key — that bright-line separation is enforced
    # by the keys themselves: a clinical token cannot be verified by the
    # platform service, and vice versa, even if the claims look right.
    jwt_signing_key: SecretStr = Field(
        default_factory=lambda: SecretStr(secrets.token_urlsafe(32)),
    )

    # Lockout policy
    failed_login_lock_threshold: int = 5
    lockout_minutes: int = 15

    # CORS — admin UI lands later; for now the only consumer is curl/scripts.
    admin_ui_origin: str = "http://localhost:3001"

    log_level: str = "INFO"
    sql_echo: bool = False


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
