"""The Tenant model.

Each tenant represents one customer organization (typically a single LTC
facility, sometimes a chain that buys per-facility seats). Tenant lifecycle
state is the gate that controls whether real PHI can be written into the
system.

State transitions:

    sandbox  ──► pending_activation  ──► active  ──► suspended  ──► terminated
                                            ▲                          │
                                            └────── reactivate ────────┘

Only the platform service may transition tenants. The clinical API reads
state and enforces it (see nexus_care_tenancy.assert_can_write_phi).
"""

from __future__ import annotations

from sqlalchemy import CheckConstraint, String, text
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

    # Display name for the facility/organization (shown to users in the UI).
    name: Mapped[str] = mapped_column(String(200), nullable=False)

    # Short user-typed code used at login alongside PIN. Unique system-wide.
    # Format constraint enforced at the application layer (lowercase
    # alphanumeric + dashes, 3-32 chars). Two facilities cannot have the same.
    facility_code: Mapped[str] = mapped_column(
        String(32), nullable=False, unique=True, index=True
    )

    # Lifecycle state — see TenantState in nexus_care_tenancy. Stored as a
    # plain string with a CHECK constraint so we can transition without
    # creating a Postgres enum (which is painful to alter).
    state: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        server_default=text("'sandbox'"),
        index=True,
    )

    # Region pin — every tenant lives in a single region for data residency.
    # 'us-central' is the only value at launch. Adding 'us-east', 'eu-west',
    # etc. is just a new row value plus a Helm deployment in that region.
    region_code: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        server_default=text("'us-central'"),
    )
