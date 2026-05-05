"""Tenant lifecycle actions exposed on the clinical API.

Only one endpoint here in tranche 4: a supervisor can request that their
tenant move from `sandbox` to `pending_activation`. This is the only state
transition any clinical user can initiate. All other transitions live in
the platform service and require platform-admin auth.

This split — supervisors can request, platform-admins approve — matches how
real SaaS activations work and makes the BAA gate auditable.
"""

from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, HTTPException, status
from nexus_care_db import Tenant
from pydantic import BaseModel
from sqlalchemy.orm import Session

from nexus_care_api.deps import AuthenticatedUser, get_db, require_user

router = APIRouter(prefix="/me/tenant", tags=["tenant-lifecycle"])


class RequestActivationResponse(BaseModel):
    tenant_id: int
    state: str
    activation_requested_at: dt.datetime | None
    message: str


@router.post(
    "/request-activation",
    response_model=RequestActivationResponse,
    status_code=status.HTTP_200_OK,
)
def request_activation(
    user: AuthenticatedUser = Depends(require_user),
    db: Session = Depends(get_db),
) -> RequestActivationResponse:
    """Supervisor: request that the current tenant transition from sandbox to
    pending_activation. Platform-admins must approve to reach `active`.

    Only supervisors and tenant_admins may call this. Sandbox is the only
    valid starting state. The endpoint is idempotent — calling it again
    while already in pending_activation returns the existing state instead
    of erroring.
    """
    if user.role not in {"supervisor", "tenant_admin"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only supervisors or tenant administrators can request activation",
        )

    tenant = db.get(Tenant, user.tenant_id)
    if tenant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

    if tenant.state == "pending_activation":
        return RequestActivationResponse(
            tenant_id=tenant.id,
            state=tenant.state,
            activation_requested_at=tenant.activation_requested_at,
            message="Activation already requested. Awaiting platform-admin approval.",
        )

    if tenant.state != "sandbox":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Cannot request activation from state {tenant.state!r}. "
                "Only tenants in 'sandbox' can be transitioned this way."
            ),
        )

    now = dt.datetime.now(dt.UTC)
    tenant.state = "pending_activation"
    tenant.activation_requested_by_user_id = user.id
    tenant.activation_requested_at = now
    db.commit()
    db.refresh(tenant)

    return RequestActivationResponse(
        tenant_id=tenant.id,
        state=tenant.state,
        activation_requested_at=tenant.activation_requested_at,
        message=(
            "Activation requested. A Nexus Care AI administrator will review "
            "your BAA and identity verification before activating real-PHI access."
        ),
    )
