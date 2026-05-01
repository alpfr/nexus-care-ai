"""The User model.

Users are the people who log in. Every user belongs to exactly one tenant.
Authentication is PIN + facility-code; the facility code is on the tenant,
the PIN hash and role are here.

A user's PIN is unique within their tenant. Two users in different tenants
can have the same PIN (independent namespaces).

Role is a single string per user — no multi-role assignment in v1. If a
user needs different permissions on different days they get separate user
records (matches how LTC facilities actually staff).
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from nexus_care_db.base import PLATFORM_SCHEMA, Base, TimestampMixin


class User(Base, TimestampMixin):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("tenant_id", "pin_hash_lookup", name="user_unique_pin_per_tenant"),
        CheckConstraint(
            "role IN ('nurse', 'med_tech', 'caregiver', 'supervisor', "
            "'tenant_admin', 'platform_admin')",
            name="user_role_valid",
        ),
        {"schema": PLATFORM_SCHEMA},
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    tenant_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey(f"{PLATFORM_SCHEMA}.tenants.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    # Display name. PHI-adjacent but not PHI itself (it's the staff member's
    # name, not a patient's). Still treated with care — not logged in detail.
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)

    # The Argon2id PHC string. NEVER queried by; we always look up by tenant +
    # pin_hash_lookup, then verify the PIN against this hash.
    pin_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    # A short non-secret index field used to find candidate users fast.
    # In v1 this is an opaque random string assigned at user creation —
    # functionally the user's "username" but we don't expose it. The login
    # flow looks up tenant by facility_code, then iterates candidate users
    # by recently-active and verifies the PIN. For now we just need a
    # uniqueness target so two users in the same tenant can't get added
    # with colliding lookup keys. This will be revisited when login UX is
    # finalized.
    pin_hash_lookup: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    role: Mapped[str] = mapped_column(String(32), nullable=False)

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

    # ---- Token revocation timestamp ----
    # Tokens with iat <= this value are rejected. Bump this column to invalidate
    # every outstanding token for this user (badge revoked, lost device, etc.).
    # Stored as Unix seconds for cheap comparison against JWT iat.
    tokens_invalid_after: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("0")
    )

    last_login_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
