"""Medication order endpoints.

  GET    /api/residents/{resident_id}/medication-orders   — list orders for a resident
  POST   /api/residents/{resident_id}/medication-orders   — write a new order
  GET    /api/medication-orders/{id}                       — order detail
  PATCH  /api/medication-orders/{id}                       — limited update
  POST   /api/medication-orders/{id}/transition            — change state

State transitions enforced here mirror the model docstring:
    pending  → active       (activate the order)
    pending  → discontinued  (cancel before active)
    active   → held          (temporarily pause)
    active   → discontinued
    held     → active        (resume)
    held     → discontinued
    discontinued → (terminal)

This is the authoritative endpoint for any state change. Only supervisors
or tenant_admins can create or activate orders. Nurses can transition
active orders to held / discontinued (with a reason).
"""

from __future__ import annotations

import datetime as dt
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from nexus_care_db import Medication, MedicationOrder, Resident
from nexus_care_tenancy import assert_can_write_phi, current_tenant_id

from nexus_care_api.deps import AuthenticatedUser, get_db, require_user
from nexus_care_api.routes.clinical._audit import record_audit

# Two routers — one mounted under /residents (for nested list+create) and
# one for top-level /medication-orders (for detail + state transitions).
nested_router = APIRouter(prefix="/residents", tags=["medication-orders"])
flat_router = APIRouter(prefix="/medication-orders", tags=["medication-orders"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------
OrderStatus = Literal["pending", "active", "held", "discontinued"]
Route = Literal[
    "oral", "sublingual", "topical", "transdermal", "inhaled",
    "nebulized", "subcutaneous", "intramuscular", "intravenous",
    "rectal", "ophthalmic", "otic", "nasal", "other",
]


class MedicationOrderOut(BaseModel):
    id: int
    resident_id: int
    medication_id: int
    medication_display_name: str
    medication_schedule: str
    dose: str
    route: Route
    frequency: str
    is_prn: bool
    prn_indication: str | None
    prn_max_doses_per_24h: int | None
    indication: str
    instructions: str | None
    prescriber_name: str
    start_date: dt.date
    end_date: dt.date | None
    status: OrderStatus
    status_reason: str | None
    witness_required: bool
    discontinued_at: dt.datetime | None
    created_at: dt.datetime
    updated_at: dt.datetime

    @classmethod
    def from_model(cls, o: MedicationOrder, med: Medication) -> "MedicationOrderOut":
        return cls(
            id=o.id,
            resident_id=o.resident_id,
            medication_id=o.medication_id,
            medication_display_name=med.display_name,
            medication_schedule=med.schedule,
            dose=o.dose,
            route=o.route,  # type: ignore[arg-type]
            frequency=o.frequency,
            is_prn=o.is_prn,
            prn_indication=o.prn_indication,
            prn_max_doses_per_24h=o.prn_max_doses_per_24h,
            indication=o.indication,
            instructions=o.instructions,
            prescriber_name=o.prescriber_name,
            start_date=o.start_date,
            end_date=o.end_date,
            status=o.status,  # type: ignore[arg-type]
            status_reason=o.status_reason,
            witness_required=o.witness_required,
            discontinued_at=o.discontinued_at,
            created_at=o.created_at,
            updated_at=o.updated_at,
        )


class CreateMedicationOrderRequest(BaseModel):
    medication_id: int
    dose: str = Field(min_length=1, max_length=64)
    route: Route
    frequency: str = Field(min_length=1, max_length=128)
    is_prn: bool = False
    prn_indication: str | None = Field(default=None, max_length=255)
    prn_max_doses_per_24h: int | None = Field(default=None, ge=1, le=24)
    indication: str = Field(min_length=1, max_length=255)
    instructions: str | None = None
    prescriber_name: str = Field(min_length=1, max_length=200)
    start_date: dt.date
    end_date: dt.date | None = None
    activate_immediately: bool = Field(
        default=True,
        description="If true, status starts as 'active'; otherwise 'pending'.",
    )

    @model_validator(mode="after")
    def _check_prn_consistency(self) -> "CreateMedicationOrderRequest":
        if self.is_prn and not self.prn_indication:
            raise ValueError("prn_indication is required when is_prn is true")
        if not self.is_prn and (
            self.prn_indication or self.prn_max_doses_per_24h is not None
        ):
            raise ValueError(
                "prn_indication / prn_max_doses_per_24h require is_prn to be true"
            )
        if self.end_date and self.end_date < self.start_date:
            raise ValueError("end_date cannot be before start_date")
        return self


class UpdateMedicationOrderRequest(BaseModel):
    """Limited update — clinical safety dictates that the dose / route /
    medication of an existing order should not be silently editable.
    Substantial changes should be a new order with the prior one
    discontinued. We allow only metadata cleanups here.
    """

    instructions: str | None = None
    end_date: dt.date | None = None


class TransitionOrderRequest(BaseModel):
    target_status: OrderStatus
    reason: str | None = Field(
        default=None,
        max_length=500,
        description="Required for transitions to 'held' or 'discontinued'.",
    )


# Legal transitions — enforced server-side.
_LEGAL: dict[str, set[OrderStatus]] = {
    "pending": {"active", "discontinued"},
    "active": {"held", "discontinued"},
    "held": {"active", "discontinued"},
    "discontinued": set(),
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _scoped_order(stmt):
    return stmt.where(MedicationOrder.tenant_id == current_tenant_id())


def _load_order_with_med(
    db: Session, order_id: int
) -> tuple[MedicationOrder, Medication]:
    order = db.execute(
        _scoped_order(select(MedicationOrder).where(MedicationOrder.id == order_id))
    ).scalar_one_or_none()
    if order is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Order not found")
    med = db.get(Medication, order.medication_id)
    if med is None:
        # Should be impossible given the FK, but defend the type system.
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Order medication not found")
    return order, med


# ---------------------------------------------------------------------------
# Nested routes: /residents/{resident_id}/medication-orders
# ---------------------------------------------------------------------------
@nested_router.get(
    "/{resident_id}/medication-orders",
    response_model=list[MedicationOrderOut],
)
def list_orders_for_resident(
    resident_id: int,
    include: str = Query(
        default="active",
        pattern="^(active|all|discontinued|pending|held)$",
    ),
    _user: AuthenticatedUser = Depends(require_user),
    db: Session = Depends(get_db),
) -> list[MedicationOrderOut]:
    # Verify the resident exists in this tenant.
    resident = db.execute(
        select(Resident)
        .where(Resident.tenant_id == current_tenant_id())
        .where(Resident.id == resident_id)
    ).scalar_one_or_none()
    if resident is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Resident not found")

    stmt = (
        _scoped_order(
            select(MedicationOrder).where(MedicationOrder.resident_id == resident_id)
        )
        .order_by(MedicationOrder.start_date.desc(), MedicationOrder.id.desc())
    )
    if include == "active":
        stmt = stmt.where(MedicationOrder.status == "active")
    elif include in {"discontinued", "pending", "held"}:
        stmt = stmt.where(MedicationOrder.status == include)
    orders = db.execute(stmt).scalars().all()

    # Bulk-fetch medications to avoid N+1 in serialization.
    med_ids = {o.medication_id for o in orders}
    meds = (
        db.execute(select(Medication).where(Medication.id.in_(med_ids)))
        .scalars()
        .all()
        if med_ids
        else []
    )
    med_by_id = {m.id: m for m in meds}
    return [MedicationOrderOut.from_model(o, med_by_id[o.medication_id]) for o in orders]


@nested_router.post(
    "/{resident_id}/medication-orders",
    response_model=MedicationOrderOut,
    status_code=status.HTTP_201_CREATED,
)
def create_order(
    resident_id: int,
    payload: CreateMedicationOrderRequest,
    user: AuthenticatedUser = Depends(require_user),
    db: Session = Depends(get_db),
) -> MedicationOrderOut:
    if user.role not in {"supervisor", "tenant_admin"}:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Only supervisors or tenant administrators can write medication orders",
        )
    assert_can_write_phi()

    resident = db.execute(
        select(Resident)
        .where(Resident.tenant_id == current_tenant_id())
        .where(Resident.id == resident_id)
    ).scalar_one_or_none()
    if resident is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Resident not found")
    if resident.status != "admitted":
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Cannot place a medication order against a discharged or deceased resident",
        )

    medication = db.execute(
        select(Medication)
        .where(Medication.tenant_id == current_tenant_id())
        .where(Medication.id == payload.medication_id)
    ).scalar_one_or_none()
    if medication is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Medication not in formulary")
    if not medication.is_active:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Medication is inactive in the formulary; reactivate it first",
        )

    order = MedicationOrder(
        tenant_id=current_tenant_id(),
        resident_id=resident.id,
        medication_id=medication.id,
        dose=payload.dose,
        route=payload.route,
        frequency=payload.frequency,
        is_prn=payload.is_prn,
        prn_indication=payload.prn_indication,
        prn_max_doses_per_24h=payload.prn_max_doses_per_24h,
        indication=payload.indication,
        instructions=payload.instructions,
        prescriber_name=payload.prescriber_name,
        start_date=payload.start_date,
        end_date=payload.end_date,
        status="active" if payload.activate_immediately else "pending",
        witness_required=medication.is_controlled,  # auto-flag controlled meds
    )
    db.add(order)
    db.flush()

    record_audit(
        db,
        actor_user_id=user.id,
        action="create",
        entity_type="medication_order",
        entity_id=str(order.id),
        summary=(
            f"Order: {medication.display_name} {order.dose} {order.route} "
            f"{order.frequency} for resident {resident.id}"
        ),
        provenance_data={
            "resident_id": resident.id,
            "medication_id": medication.id,
            "is_prn": order.is_prn,
            "controlled": medication.is_controlled,
            "initial_status": order.status,
        },
    )
    db.commit()
    db.refresh(order)
    return MedicationOrderOut.from_model(order, medication)


# ---------------------------------------------------------------------------
# Flat routes: /medication-orders/{id}
# ---------------------------------------------------------------------------
@flat_router.get("/{order_id}", response_model=MedicationOrderOut)
def get_order(
    order_id: int,
    _user: AuthenticatedUser = Depends(require_user),
    db: Session = Depends(get_db),
) -> MedicationOrderOut:
    order, med = _load_order_with_med(db, order_id)
    return MedicationOrderOut.from_model(order, med)


@flat_router.patch("/{order_id}", response_model=MedicationOrderOut)
def update_order(
    order_id: int,
    payload: UpdateMedicationOrderRequest,
    user: AuthenticatedUser = Depends(require_user),
    db: Session = Depends(get_db),
) -> MedicationOrderOut:
    if user.role not in {"supervisor", "tenant_admin"}:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Only supervisors or tenant administrators can update orders",
        )
    assert_can_write_phi()

    order, med = _load_order_with_med(db, order_id)
    if order.status == "discontinued":
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Cannot edit a discontinued order; write a new one if needed",
        )

    update_data = payload.model_dump(exclude_unset=True)
    fields_changed = [k for k, v in update_data.items() if getattr(order, k) != v]
    if not fields_changed:
        return MedicationOrderOut.from_model(order, med)
    for key in fields_changed:
        setattr(order, key, update_data[key])

    record_audit(
        db,
        actor_user_id=user.id,
        action="update",
        entity_type="medication_order",
        entity_id=str(order.id),
        summary=f"Updated: {', '.join(fields_changed)}",
        provenance_data={"fields_changed": fields_changed},
    )
    db.commit()
    db.refresh(order)
    return MedicationOrderOut.from_model(order, med)


@flat_router.post("/{order_id}/transition", response_model=MedicationOrderOut)
def transition_order(
    order_id: int,
    payload: TransitionOrderRequest,
    user: AuthenticatedUser = Depends(require_user),
    db: Session = Depends(get_db),
) -> MedicationOrderOut:
    """Change order status. Nurses may move active→held (with reason);
    only supervisors/tenant_admins can move pending→active or do
    discontinuations."""
    assert_can_write_phi()

    order, med = _load_order_with_med(db, order_id)
    current = order.status
    target = payload.target_status

    if current == target:
        return MedicationOrderOut.from_model(order, med)

    legal = _LEGAL.get(current, set())
    if target not in legal:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Illegal transition: {current!r} → {target!r}. "
            f"Legal targets from {current!r}: {sorted(legal) or 'none (terminal)'}",
        )

    # Permission gating.
    activation_transitions = {("pending", "active"), ("held", "active")}
    requires_supervisor = (
        target == "discontinued" or (current, target) in activation_transitions
    )
    if requires_supervisor and user.role not in {"supervisor", "tenant_admin"}:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Only supervisors or tenant administrators can perform this transition",
        )

    # Reason required for held / discontinued.
    if target in {"held", "discontinued"} and not payload.reason:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"reason is required to transition to {target!r}",
        )

    order.status = target
    if target == "discontinued":
        order.discontinued_at = dt.datetime.now(dt.UTC)
    if target in {"held", "discontinued"}:
        order.status_reason = payload.reason
    elif target == "active":
        # Clearing held reason on resume.
        order.status_reason = None

    record_audit(
        db,
        actor_user_id=user.id,
        action="update",
        entity_type="medication_order",
        entity_id=str(order.id),
        summary=f"Transitioned {current} → {target}",
        provenance_data={
            "previous_status": current,
            "new_status": target,
            "reason": payload.reason,
        },
    )
    db.commit()
    db.refresh(order)
    return MedicationOrderOut.from_model(order, med)
