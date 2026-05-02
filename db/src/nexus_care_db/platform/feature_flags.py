"""FeatureFlag — per-tenant feature toggles.

Schema: each row is a (tenant_id, flag_key) pair with an enabled boolean
and an optional JSON `config` blob. Absence of a row means "use the default
for this flag" (handled by the application).

This isn't a full feature-flag system — no targeting rules, no user-level
overrides, no rollout percentages. Just "is feature X on for tenant Y."
That's enough for the things we need flags for in early phases:

  - 'ai_documentation' : turn the AI SOAP/SBAR features on/off per tenant
  - 'family_portal'    : show the family-facing surfaces or not
  - 'fhir_export'      : enable FHIR R4 DocumentReference export
  - 'mds_3_0'          : enable MDS form completion (only Medicare-certified
                         facilities need it)

When richer flag semantics are needed (probably late 2026), we either add
LaunchDarkly or extend this. Until then, simpler is better.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import (
    JSON,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from nexus_care_db.base import PLATFORM_SCHEMA, Base, TimestampMixin


class FeatureFlag(Base, TimestampMixin):
    __tablename__ = "feature_flags"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "flag_key", name="uq_feature_flags_tenant_id_flag_key"
        ),
        {"schema": PLATFORM_SCHEMA},
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    tenant_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey(f"{PLATFORM_SCHEMA}.tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    flag_key: Mapped[str] = mapped_column(String(64), nullable=False)
    enabled: Mapped[bool] = mapped_column(
        nullable=False, server_default=text("false")
    )

    # Optional config (numeric thresholds, allowed roles, etc.). Keep it
    # JSON so we don't churn the schema for every new knob.
    config: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
