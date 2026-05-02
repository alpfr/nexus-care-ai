"""The Tenant model.

Each tenant represents one customer organization (typically a single LTC
facility, sometimes a chain that buys per-facility seats). Tenant lifecycle
state is the gate that controls whether real PHI can be written into the
system.

State transitions:

    sandbox  ──► pending_activation  ──► active  ──► suspended  ──► terminated
                                            ▲                          │
                                            └────── reactivate ────────┘

Transitions:
  - sandbox → pending_activation : supervisor self-serves (clinical API)
  - pending_activation → active  : platform-admin only (platform API)
  - active → suspended           : platform-admin only (e.g., past-due)
  - suspended → active           : platform-admin only (reactivation)
  - any → terminated             : platform-admin only

State + activation-pipeline columns are all here — keeping the lifecycle
state and the artifacts that produced it co-located makes auditing easier.
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from nexus_care_db.base import PLATFORM_SCHEMA, Base, TimestampMixin


class Tenant(Base, TimestampMixin):
    __tablename__ = "tenants"
    __table_args__ = (
        CheckConstraint(
            "state IN ('sandbox', 'pending_activation', 'active', 'suspended', 'terminated')",
            name="tenant_state_valid",
        ),
        {"schema": PLATFORM_SCHEMA},
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    facility_code: Mapped[str] = mapped_column(
        String(32), nullable=False, unique=True, index=True
    )
    state: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        server_default=text("'sandbox'"),
        index=True,
    )
    region_code: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        server_default=text("'us-central'"),
    )

    # ---- Activation pipeline ----
    # The supervisor who initiated the request to leave sandbox. Set when
    # state transitions sandbox → pending_activation.
    activation_requested_by_user_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey(f"{PLATFORM_SCHEMA}.users.id", ondelete="SET NULL"),
        nullable=True,
    )
    activation_requested_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Platform admin who approved the transition to active.
    activated_by_admin_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey(
            f"{PLATFORM_SCHEMA}.platform_admins.id",
            ondelete="SET NULL",
            use_alter=True,  # avoid circular FK at table creation time
            name="fk_tenants_activated_by_admin_id_platform_admins",
        ),
        nullable=True,
    )
    activated_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # External references to BAA + identity verification. In tranche 4 these
    # are free-text — when we wire DocuSign/PandaDoc and Persona/Stripe Identity
    # in tranche 9, they hold the artifact IDs from those providers.
    baa_artifact_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    identity_verification_ref: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )

    # Why a tenant was suspended/terminated. Free-text for now; could become
    # an enum later.
    state_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
