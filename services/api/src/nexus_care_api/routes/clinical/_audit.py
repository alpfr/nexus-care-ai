"""Audit log helper for clinical writes.

Every clinical mutation calls record_audit() inside the same transaction
as the write itself. If the audit insert fails, the whole transaction
rolls back — preserving the invariant that PHI mutations and audit entries
are always paired.

Reads are not audited by default in tranche 6a — listing 50 residents on
a dashboard would generate 50 audit rows per refresh, which is operationally
noisy without yet being clinically required. We'll add scoped read auditing
in tranche 9 alongside SOC 2 prep, where the requirement gets formalized.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from nexus_care_db import AuditLog
from nexus_care_tenancy import current_tenant


def record_audit(
    db: Session,
    *,
    actor_user_id: int | None,
    action: str,
    entity_type: str,
    entity_id: str | None = None,
    outcome: str = "success",
    summary: str | None = None,
    provenance_data: dict[str, Any] | None = None,
) -> None:
    """Append an audit row tied to the current tenant.

    Does NOT call db.commit() — the caller commits as part of their
    transaction so audit and PHI writes succeed or fail atomically.
    """
    ctx = current_tenant()
    db.add(
        AuditLog(
            tenant_id=ctx.tenant_id,
            actor_user_id=actor_user_id,
            tenant_state=ctx.state.value,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            outcome=outcome,
            summary=summary,
            provenance_data=provenance_data,
        )
    )
