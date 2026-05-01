"""The AuditLog model.

Append-only. Every PHI read and write produces an entry. Writes from
non-active tenants would be a bug — and they're recorded here too, with
the tenant state at the time, so we can prove the gate was honored.

Schema design notes:
  - `tenant_id` is non-null and indexed: every audit query is tenant-scoped.
  - `actor_user_id` is nullable: some events are system-generated (e.g.,
    automated retention deletions).
  - `entity_type` + `entity_id` together identify the affected resource
    (e.g., entity_type='resident', entity_id='42').
  - `tenant_state` records the lifecycle state at write time. Defending
    the PHI gate later requires this.
  - `provenance_data` is a JSON column for whatever extra context the
    write provides (request IP, route, AI model version, etc.). Stays
    flexible without schema churn.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    DateTime,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from nexus_care_db.base import TENANT_DATA_SCHEMA, Base


class AuditLog(Base):
    __tablename__ = "audit_log"
    __table_args__ = (
        # Composite indexes for the two most common queries:
        # 1) "show me everything for this resident" — by tenant + entity
        Index(
            "ix_audit_log_tenant_entity",
            "tenant_id",
            "entity_type",
            "entity_id",
            "occurred_at",
        ),
        # 2) "show me everything by this user today" — by tenant + actor
        Index(
            "ix_audit_log_tenant_actor",
            "tenant_id",
            "actor_user_id",
            "occurred_at",
        ),
        {"schema": TENANT_DATA_SCHEMA},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)

    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    # User who triggered the event (NULL for system events).
    actor_user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Tenant state at the moment of write. Critical for defending the PHI
    # gate later — we can prove no PHI write happened from a non-active
    # tenant by querying audit rows where action='create' and tenant_state
    # != 'active' and entity_type IN (phi_tables).
    tenant_state: Mapped[str] = mapped_column(String(32), nullable=False)

    # The action and resource — same vocabulary as nexus_care_auth.permissions.
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Outcome: success / forbidden / error. Failed access attempts are
    # logged just as carefully as successful ones.
    outcome: Mapped[str] = mapped_column(String(16), nullable=False)

    # Free-form summary for human review. Must NOT contain PHI — the
    # observability layer scrubs PHI before it gets here. Detailed structured
    # context goes in `provenance_data` (also scrubbed).
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    provenance_data: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    occurred_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
