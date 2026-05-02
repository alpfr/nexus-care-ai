"""PlatformAdmin — Nexus Care AI staff who operate the SaaS platform.

These users manage tenants (lifecycle, billing, feature flags) but cannot
read clinical PHI. Authentication is email+password (Argon2id-hashed) with
the same lockout + revocation primitives as clinical users, just keyed on
email instead of PIN.

Platform admins are NOT scoped to a tenant (tenant_id is nullable) — they
operate at the platform level, across tenants. Their permissions are
strictly limited by the `can()` helper in nexus_care_auth.permissions to
non-PHI resources.
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Integer,
    String,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from nexus_care_db.base import PLATFORM_SCHEMA, Base, TimestampMixin


class PlatformAdmin(Base, TimestampMixin):
    __tablename__ = "platform_admins"
    __table_args__ = (
        {"schema": PLATFORM_SCHEMA},
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    email: Mapped[str] = mapped_column(
        String(320), nullable=False, unique=True, index=True
    )
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )

    # ---- Lockout (5 failed attempts = 15-minute lock) ----
    failed_login_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    locked_until: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # ---- Token revocation timestamp (Unix seconds) ----
    tokens_invalid_after: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("0")
    )

    last_login_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
