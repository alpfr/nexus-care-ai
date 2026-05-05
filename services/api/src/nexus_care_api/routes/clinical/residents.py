"""Resident endpoints.

  GET    /api/residents              — list (active by default, ?include=all)
  POST   /api/residents              — create (admit) a resident
  GET    /api/residents/{id}         — detail
  PATCH  /api/residents/{id}         — update demographics / clinical info
  POST   /api/residents/{id}/discharge — discharge (status transition)

Every handler is tenant-scoped via require_user (which sets the context).
Writes call assert_can_write_phi() before mutating, so sandbox tenants get
a clean 403 with a hint about activation.
"""

from __future__ import annotations

import datetime as dt
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from nexus_care_auth import can
from nexus_care_db import Resident
from nexus_care_tenancy import assert_can_write_phi, current_tenant_id
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from nexus_care_api.deps import AuthenticatedUser, get_db, require_user
from nexus_care_api.routes.clinical._audit import record_audit

router = APIRouter(prefix="/residents", tags=["residents"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------
ResidentStatus = Literal["admitted", "discharged", "deceased"]
CodeStatus = Literal["full", "dnr", "dni", "dnr_dni", "comfort_only", "unknown"]
FallRisk = Literal["low", "moderate", "high", "unassessed"]


class ResidentSummary(BaseModel):
    id: int
    legal_first_name: str
    legal_last_name: str
    preferred_name: str | None
    display_name: str
    date_of_birth: dt.date
    admission_date: dt.date
    status: ResidentStatus
    room: str | None
    bed: str | None
    code_status: CodeStatus
    fall_risk: FallRisk

    @classmethod
    def from_model(cls, r: Resident) -> ResidentSummary:
        return cls(
            id=r.id,
            legal_first_name=r.legal_first_name,
            legal_last_name=r.legal_last_name,
            preferred_name=r.preferred_name,
            display_name=r.display_name,
            date_of_birth=r.date_of_birth,
            admission_date=r.admission_date,
            status=r.status,  # type: ignore[arg-type]
            room=r.room,
            bed=r.bed,
            code_status=r.code_status,  # type: ignore[arg-type]
            fall_risk=r.fall_risk,  # type: ignore[arg-type]
        )


class ResidentDetail(ResidentSummary):
    gender: str | None
    discharge_date: dt.date | None
    allergies_summary: str | None
    dietary_restrictions: str | None
    primary_physician_name: str | None
    emergency_contact_name: str | None
    emergency_contact_relationship: str | None
    emergency_contact_phone: str | None
    chart_note: str | None
    created_at: dt.datetime
    updated_at: dt.datetime

    @classmethod
    def from_model(cls, r: Resident) -> ResidentDetail:
        base = ResidentSummary.from_model(r)
        return cls(
            **base.model_dump(),
            gender=r.gender,
            discharge_date=r.discharge_date,
            allergies_summary=r.allergies_summary,
            dietary_restrictions=r.dietary_restrictions,
            primary_physician_name=r.primary_physician_name,
            emergency_contact_name=r.emergency_contact_name,
            emergency_contact_relationship=r.emergency_contact_relationship,
            emergency_contact_phone=r.emergency_contact_phone,
            chart_note=r.chart_note,
            created_at=r.created_at,
            updated_at=r.updated_at,
        )


class CreateResidentRequest(BaseModel):
    legal_first_name: str = Field(min_length=1, max_length=100)
    legal_last_name: str = Field(min_length=1, max_length=100)
    preferred_name: str | None = Field(default=None, max_length=100)
    date_of_birth: dt.date
    gender: str | None = Field(default=None, max_length=50)
    admission_date: dt.date
    room: str | None = Field(default=None, max_length=16)
    bed: str | None = Field(default=None, max_length=16)
    allergies_summary: str | None = None
    code_status: CodeStatus = "unknown"
    fall_risk: FallRisk = "unassessed"
    dietary_restrictions: str | None = None
    primary_physician_name: str | None = Field(default=None, max_length=200)
    emergency_contact_name: str | None = Field(default=None, max_length=200)
    emergency_contact_relationship: str | None = Field(default=None, max_length=64)
    emergency_contact_phone: str | None = Field(default=None, max_length=32)
    chart_note: str | None = None

    @field_validator("date_of_birth")
    @classmethod
    def dob_must_be_past(cls, v: dt.date) -> dt.date:
        if v >= dt.date.today():
            raise ValueError("date_of_birth must be in the past")
        return v


class UpdateResidentRequest(BaseModel):
    preferred_name: str | None = Field(default=None, max_length=100)
    gender: str | None = Field(default=None, max_length=50)
    room: str | None = Field(default=None, max_length=16)
    bed: str | None = Field(default=None, max_length=16)
    allergies_summary: str | None = None
    code_status: CodeStatus | None = None
    fall_risk: FallRisk | None = None
    dietary_restrictions: str | None = None
    primary_physician_name: str | None = Field(default=None, max_length=200)
    emergency_contact_name: str | None = Field(default=None, max_length=200)
    emergency_contact_relationship: str | None = Field(default=None, max_length=64)
    emergency_contact_phone: str | None = Field(default=None, max_length=32)
    chart_note: str | None = None


class DischargeRequest(BaseModel):
    discharge_date: dt.date
    reason: str | None = Field(default=None, max_length=500)
    deceased: bool = Field(default=False)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _scoped(stmt):
    return stmt.where(Resident.tenant_id == current_tenant_id())


def _check_room_bed_unique(
    db: Session,
    *,
    room: str | None,
    bed: str | None,
    exclude_id: int | None = None,
) -> None:
    if room is None or bed is None:
        return
    stmt = _scoped(
        select(Resident).where(
            Resident.room == room,
            Resident.bed == bed,
            Resident.status == "admitted",
        )
    )
    if exclude_id is not None:
        stmt = stmt.where(Resident.id != exclude_id)
    conflict = db.execute(stmt).scalar_one_or_none()
    if conflict is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Room {room} bed {bed} is already occupied by an active resident "
                f"(id={conflict.id}). Discharge or move that resident first."
            ),
        )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@router.get("", response_model=list[ResidentSummary])
def list_residents(
    include: str = Query(
        default="active",
        pattern="^(active|all|discharged)$",
        description="active (default), all, or discharged",
    ),
    user: AuthenticatedUser = Depends(require_user),
    db: Session = Depends(get_db),
) -> list[ResidentSummary]:
    if not can(user, "read", "resident"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient permissions")

    stmt = _scoped(select(Resident)).order_by(Resident.legal_last_name, Resident.legal_first_name)
    if include == "active":
        stmt = stmt.where(Resident.status == "admitted")
    elif include == "discharged":
        stmt = stmt.where(or_(Resident.status == "discharged", Resident.status == "deceased"))

    rows = db.execute(stmt).scalars().all()
    return [ResidentSummary.from_model(r) for r in rows]


@router.get("/{resident_id}", response_model=ResidentDetail)
def get_resident(
    resident_id: int,
    user: AuthenticatedUser = Depends(require_user),
    db: Session = Depends(get_db),
) -> ResidentDetail:
    if not can(user, "read", "resident"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient permissions")

    resident = db.execute(
        _scoped(select(Resident).where(Resident.id == resident_id))
    ).scalar_one_or_none()
    if resident is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Resident not found")
    return ResidentDetail.from_model(resident)


@router.post("", response_model=ResidentDetail, status_code=status.HTTP_201_CREATED)
def admit_resident(
    payload: CreateResidentRequest,
    user: AuthenticatedUser = Depends(require_user),
    db: Session = Depends(get_db),
) -> ResidentDetail:
    if user.role not in {"supervisor", "tenant_admin"}:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Only supervisors or tenant administrators can admit residents",
        )
    assert_can_write_phi()

    _check_room_bed_unique(db, room=payload.room, bed=payload.bed)

    resident = Resident(
        tenant_id=current_tenant_id(),
        status="admitted",
        **payload.model_dump(),
    )
    db.add(resident)
    db.flush()

    record_audit(
        db,
        actor_user_id=user.id,
        action="create",
        entity_type="resident",
        entity_id=str(resident.id),
        summary=f"Admitted {resident.legal_last_name}",
    )
    db.commit()
    db.refresh(resident)
    return ResidentDetail.from_model(resident)


@router.patch("/{resident_id}", response_model=ResidentDetail)
def update_resident(
    resident_id: int,
    payload: UpdateResidentRequest,
    user: AuthenticatedUser = Depends(require_user),
    db: Session = Depends(get_db),
) -> ResidentDetail:
    if not can(user, "update", "resident"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient permissions")
    assert_can_write_phi()

    resident = db.execute(
        _scoped(select(Resident).where(Resident.id == resident_id))
    ).scalar_one_or_none()
    if resident is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Resident not found")

    if resident.status != "admitted":
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Cannot update a discharged or deceased resident's chart",
        )

    fields_changed: list[str] = []
    update_data = payload.model_dump(exclude_unset=True)

    new_room = update_data.get("room", resident.room)
    new_bed = update_data.get("bed", resident.bed)
    if (new_room, new_bed) != (resident.room, resident.bed):
        _check_room_bed_unique(db, room=new_room, bed=new_bed, exclude_id=resident.id)

    for key, value in update_data.items():
        if getattr(resident, key) != value:
            setattr(resident, key, value)
            fields_changed.append(key)

    if not fields_changed:
        return ResidentDetail.from_model(resident)

    record_audit(
        db,
        actor_user_id=user.id,
        action="update",
        entity_type="resident",
        entity_id=str(resident.id),
        summary=f"Updated: {', '.join(fields_changed)}",
        provenance_data={"fields_changed": fields_changed},
    )
    db.commit()
    db.refresh(resident)
    return ResidentDetail.from_model(resident)


@router.post("/{resident_id}/discharge", response_model=ResidentDetail)
def discharge_resident(
    resident_id: int,
    payload: DischargeRequest,
    user: AuthenticatedUser = Depends(require_user),
    db: Session = Depends(get_db),
) -> ResidentDetail:
    if user.role not in {"supervisor", "tenant_admin"}:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Only supervisors or tenant administrators can discharge residents",
        )
    assert_can_write_phi()

    resident = db.execute(
        _scoped(select(Resident).where(Resident.id == resident_id))
    ).scalar_one_or_none()
    if resident is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Resident not found")

    if resident.status != "admitted":
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Resident is already in state {resident.status!r}; cannot discharge",
        )

    resident.status = "deceased" if payload.deceased else "discharged"
    resident.discharge_date = payload.discharge_date
    resident.room = None
    resident.bed = None

    record_audit(
        db,
        actor_user_id=user.id,
        action="update",
        entity_type="resident",
        entity_id=str(resident.id),
        summary=f"Discharged ({resident.status})",
        provenance_data={
            "discharge_date": payload.discharge_date.isoformat(),
            "deceased": payload.deceased,
            "reason": payload.reason,
        },
    )
    db.commit()
    db.refresh(resident)
    return ResidentDetail.from_model(resident)
