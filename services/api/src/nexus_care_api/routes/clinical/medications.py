"""Medication catalog endpoints.

  GET    /api/medications              — list (active by default)
  POST   /api/medications              — add a drug to the formulary
  GET    /api/medications/{id}         — detail
  PATCH  /api/medications/{id}         — update (rename, deactivate, etc.)

Medications are tenant-scoped — each facility curates its own formulary.
Future enhancement: a "shared formulary" feature flag for chains.

Note that the medication catalog is technically NOT PHI — it's data about
drugs, not patients. We still scope it by tenant (different formularies
per facility) but we don't gate writes behind the PHI active-state
requirement. A sandbox tenant CAN populate its formulary while it's still
in sandbox; that's how the demo data gets created.
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from nexus_care_db import Medication
from nexus_care_tenancy import current_tenant_id

from nexus_care_api.deps import AuthenticatedUser, get_db, require_user
from nexus_care_api.routes.clinical._audit import record_audit

router = APIRouter(prefix="/medications", tags=["medications"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------
DEASchedule = Literal["none", "II", "III", "IV", "V"]
MedForm = Literal[
    "tablet", "capsule", "liquid", "oral_solution", "suspension",
    "patch", "cream", "ointment", "inhaler", "nebulizer_solution",
    "injection", "suppository", "eye_drop", "ear_drop", "other",
]


class MedicationOut(BaseModel):
    id: int
    name: str
    brand_name: str | None
    strength: str
    form: MedForm
    schedule: DEASchedule
    is_active: bool
    is_controlled: bool
    notes: str | None
    display_name: str

    @classmethod
    def from_model(cls, m: Medication) -> "MedicationOut":
        return cls(
            id=m.id,
            name=m.name,
            brand_name=m.brand_name,
            strength=m.strength,
            form=m.form,  # type: ignore[arg-type]
            schedule=m.schedule,  # type: ignore[arg-type]
            is_active=m.is_active,
            is_controlled=m.is_controlled,
            notes=m.notes,
            display_name=m.display_name,
        )


class CreateMedicationRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    brand_name: str | None = Field(default=None, max_length=200)
    strength: str = Field(min_length=1, max_length=64)
    form: MedForm
    schedule: DEASchedule = "none"
    notes: str | None = None


class UpdateMedicationRequest(BaseModel):
    brand_name: str | None = Field(default=None, max_length=200)
    is_active: bool | None = None
    notes: str | None = None
    schedule: DEASchedule | None = None


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
def _scoped(stmt):
    return stmt.where(Medication.tenant_id == current_tenant_id())


@router.get("", response_model=list[MedicationOut])
def list_medications(
    include: str = Query(
        default="active",
        pattern="^(active|all|inactive)$",
    ),
    q: str | None = Query(
        default=None,
        max_length=100,
        description="Optional name substring filter (case-insensitive).",
    ),
    _user: AuthenticatedUser = Depends(require_user),
    db: Session = Depends(get_db),
) -> list[MedicationOut]:
    stmt = _scoped(select(Medication)).order_by(Medication.name, Medication.strength)
    if include == "active":
        stmt = stmt.where(Medication.is_active.is_(True))
    elif include == "inactive":
        stmt = stmt.where(Medication.is_active.is_(False))
    if q:
        stmt = stmt.where(Medication.name.ilike(f"%{q}%"))
    rows = db.execute(stmt).scalars().all()
    return [MedicationOut.from_model(m) for m in rows]


@router.get("/{medication_id}", response_model=MedicationOut)
def get_medication(
    medication_id: int,
    _user: AuthenticatedUser = Depends(require_user),
    db: Session = Depends(get_db),
) -> MedicationOut:
    med = db.execute(
        _scoped(select(Medication).where(Medication.id == medication_id))
    ).scalar_one_or_none()
    if med is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Medication not found")
    return MedicationOut.from_model(med)


@router.post("", response_model=MedicationOut, status_code=status.HTTP_201_CREATED)
def create_medication(
    payload: CreateMedicationRequest,
    user: AuthenticatedUser = Depends(require_user),
    db: Session = Depends(get_db),
) -> MedicationOut:
    if user.role not in {"supervisor", "tenant_admin"}:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Only supervisors or tenant administrators can edit the formulary",
        )

    # Catalog uniqueness per tenant.
    duplicate = db.execute(
        _scoped(
            select(Medication).where(
                Medication.name.ilike(payload.name),
                Medication.strength == payload.strength,
            )
        )
    ).scalar_one_or_none()
    if duplicate is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"{payload.name} {payload.strength} is already in the formulary",
        )

    med = Medication(tenant_id=current_tenant_id(), **payload.model_dump())
    db.add(med)
    db.flush()

    record_audit(
        db,
        actor_user_id=user.id,
        action="create",
        entity_type="medication",
        entity_id=str(med.id),
        summary=f"Added {med.display_name}",
    )
    db.commit()
    db.refresh(med)
    return MedicationOut.from_model(med)


@router.patch("/{medication_id}", response_model=MedicationOut)
def update_medication(
    medication_id: int,
    payload: UpdateMedicationRequest,
    user: AuthenticatedUser = Depends(require_user),
    db: Session = Depends(get_db),
) -> MedicationOut:
    if user.role not in {"supervisor", "tenant_admin"}:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Only supervisors or tenant administrators can edit the formulary",
        )

    med = db.execute(
        _scoped(select(Medication).where(Medication.id == medication_id))
    ).scalar_one_or_none()
    if med is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Medication not found")

    update_data = payload.model_dump(exclude_unset=True)
    fields_changed = [k for k, v in update_data.items() if getattr(med, k) != v]
    if not fields_changed:
        return MedicationOut.from_model(med)
    for key in fields_changed:
        setattr(med, key, update_data[key])

    record_audit(
        db,
        actor_user_id=user.id,
        action="update",
        entity_type="medication",
        entity_id=str(med.id),
        summary=f"Updated: {', '.join(fields_changed)}",
        provenance_data={"fields_changed": fields_changed},
    )
    db.commit()
    db.refresh(med)
    return MedicationOut.from_model(med)
