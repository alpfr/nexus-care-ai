"""Tenant lifecycle endpoints — the heart of the SaaS platform service.

Every state transition goes through PATCH /tenants/{id}/state with a
target_state in the body. The handler validates the transition is legal
(e.g., can't go directly from sandbox → active without passing through
pending_activation) and records the actor who made the change.

Transition matrix (platform-admin can do all of these):

    sandbox            → pending_activation
    pending_activation → active
    pending_activation → sandbox        (admin denies the activation request)
    active             → suspended
    suspended          → active         (reactivate)
    sandbox            → terminated
    pending_activation → terminated
    active             → terminated
    suspended          → terminated

Anything else is rejected. Once `terminated`, no further transitions allowed.

The `sandbox → pending_activation` transition can ALSO be initiated by a
supervisor through the clinical API — that endpoint lives in services/api/
routes/tenant_lifecycle.py.
"""

from __future__ import annotations

import datetime as dt
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from nexus_care_db import Tenant
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from nexus_care_platform.deps import AuthenticatedAdmin, get_db, require_admin

router = APIRouter(prefix="/tenants", tags=["tenants"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------
TenantState = Literal["sandbox", "pending_activation", "active", "suspended", "terminated"]


class TenantSummary(BaseModel):
    id: int
    name: str
    facility_code: str
    state: TenantState
    region_code: str
    created_at: dt.datetime
    activation_requested_at: dt.datetime | None = None
    activated_at: dt.datetime | None = None


class CreateTenantRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    facility_code: str = Field(
        min_length=3,
        max_length=32,
        pattern=r"^[a-z0-9-]+$",
    )
    region_code: str = Field(default="us-central", max_length=32)


class TransitionStateRequest(BaseModel):
    target_state: TenantState
    baa_artifact_ref: str | None = None
    identity_verification_ref: str | None = None
    state_reason: str | None = None


# ---------------------------------------------------------------------------
# Transition rules
# ---------------------------------------------------------------------------
_LEGAL_TRANSITIONS: dict[str, set[TenantState]] = {
    "sandbox": {"pending_activation", "terminated"},
    "pending_activation": {"active", "sandbox", "terminated"},
    "active": {"suspended", "terminated"},
    "suspended": {"active", "terminated"},
    "terminated": set(),  # terminal state
}


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@router.get("", response_model=list[TenantSummary])
def list_tenants(
    state: TenantState | None = None,
    _admin: AuthenticatedAdmin = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list[TenantSummary]:
    stmt = select(Tenant).order_by(Tenant.id)
    if state is not None:
        stmt = stmt.where(Tenant.state == state)
    rows = db.execute(stmt).scalars().all()
    return [_to_summary(t) for t in rows]


@router.post("", response_model=TenantSummary, status_code=status.HTTP_201_CREATED)
def create_tenant(
    payload: CreateTenantRequest,
    _admin: AuthenticatedAdmin = Depends(require_admin),
    db: Session = Depends(get_db),
) -> TenantSummary:
    # Reject duplicate facility codes early with a clear error.
    existing = db.execute(
        select(Tenant).where(Tenant.facility_code == payload.facility_code.lower())
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Facility code '{payload.facility_code}' already exists",
        )

    tenant = Tenant(
        name=payload.name,
        facility_code=payload.facility_code.lower(),
        state="sandbox",
        region_code=payload.region_code,
    )
    db.add(tenant)
    db.commit()
    db.refresh(tenant)
    return _to_summary(tenant)


@router.get("/{tenant_id}", response_model=TenantSummary)
def get_tenant(
    tenant_id: int,
    _admin: AuthenticatedAdmin = Depends(require_admin),
    db: Session = Depends(get_db),
) -> TenantSummary:
    tenant = db.get(Tenant, tenant_id)
    if tenant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")
    return _to_summary(tenant)


@router.patch("/{tenant_id}/state", response_model=TenantSummary)
def transition_state(
    tenant_id: int,
    payload: TransitionStateRequest,
    admin: AuthenticatedAdmin = Depends(require_admin),
    db: Session = Depends(get_db),
) -> TenantSummary:
    tenant = db.get(Tenant, tenant_id)
    if tenant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

    current = tenant.state
    target = payload.target_state

    # Idempotent: same-state transitions are no-ops, not errors.
    if current == target:
        return _to_summary(tenant)

    legal = _LEGAL_TRANSITIONS.get(current, set())
    if target not in legal:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Illegal transition: {current!r} → {target!r}. "
                f"Legal targets from {current!r}: {sorted(legal) or 'none (terminal state)'}"
            ),
        )

    now = dt.datetime.now(dt.UTC)

    # Specific transition side effects:
    if target == "active" and current == "pending_activation":
        # Require BAA + identity refs on activation. This is the gate.
        if not payload.baa_artifact_ref or not payload.identity_verification_ref:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    "baa_artifact_ref and identity_verification_ref are required "
                    "to transition to 'active'"
                ),
            )
        tenant.baa_artifact_ref = payload.baa_artifact_ref
        tenant.identity_verification_ref = payload.identity_verification_ref
        tenant.activated_by_admin_id = admin.id
        tenant.activated_at = now

    if target in {"suspended", "terminated"}:
        if not payload.state_reason:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"state_reason is required to transition to {target!r}",
            )
        tenant.state_reason = payload.state_reason

    if target == "sandbox" and current == "pending_activation":
        # Admin declined the activation request — clear the request fields.
        tenant.activation_requested_by_user_id = None
        tenant.activation_requested_at = None
        if payload.state_reason:
            tenant.state_reason = payload.state_reason

    tenant.state = target
    db.commit()
    db.refresh(tenant)
    return _to_summary(tenant)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _to_summary(tenant: Tenant) -> TenantSummary:
    return TenantSummary(
        id=tenant.id,
        name=tenant.name,
        facility_code=tenant.facility_code,
        state=tenant.state,  # type: ignore[arg-type]
        region_code=tenant.region_code,
        created_at=tenant.created_at,
        activation_requested_at=tenant.activation_requested_at,
        activated_at=tenant.activated_at,
    )
