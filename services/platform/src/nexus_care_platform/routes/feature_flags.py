"""Feature-flag management routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from nexus_care_db import FeatureFlag, Tenant

from nexus_care_platform.deps import AuthenticatedAdmin, get_db, require_admin

router = APIRouter(prefix="/feature-flags", tags=["feature-flags"])


class FeatureFlagOut(BaseModel):
    id: int
    tenant_id: int
    flag_key: str
    enabled: bool
    config: dict[str, Any] | None


class SetFlagRequest(BaseModel):
    tenant_id: int
    flag_key: str = Field(min_length=1, max_length=64, pattern=r"^[a-z][a-z0-9_]*$")
    enabled: bool
    config: dict[str, Any] | None = None


@router.get("", response_model=list[FeatureFlagOut])
def list_flags(
    tenant_id: int | None = None,
    _admin: AuthenticatedAdmin = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list[FeatureFlagOut]:
    stmt = select(FeatureFlag).order_by(FeatureFlag.tenant_id, FeatureFlag.flag_key)
    if tenant_id is not None:
        stmt = stmt.where(FeatureFlag.tenant_id == tenant_id)
    rows = db.execute(stmt).scalars().all()
    return [
        FeatureFlagOut(
            id=row.id,
            tenant_id=row.tenant_id,
            flag_key=row.flag_key,
            enabled=row.enabled,
            config=row.config,
        )
        for row in rows
    ]


@router.put("", response_model=FeatureFlagOut)
def set_flag(
    payload: SetFlagRequest,
    _admin: AuthenticatedAdmin = Depends(require_admin),
    db: Session = Depends(get_db),
) -> FeatureFlagOut:
    """Upsert: if the (tenant, flag_key) row exists, update it; otherwise create."""
    tenant = db.get(Tenant, payload.tenant_id)
    if tenant is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found"
        )

    flag = db.execute(
        select(FeatureFlag).where(
            FeatureFlag.tenant_id == payload.tenant_id,
            FeatureFlag.flag_key == payload.flag_key,
        )
    ).scalar_one_or_none()

    if flag is None:
        flag = FeatureFlag(
            tenant_id=payload.tenant_id,
            flag_key=payload.flag_key,
            enabled=payload.enabled,
            config=payload.config,
        )
        db.add(flag)
    else:
        flag.enabled = payload.enabled
        flag.config = payload.config

    db.commit()
    db.refresh(flag)
    return FeatureFlagOut(
        id=flag.id,
        tenant_id=flag.tenant_id,
        flag_key=flag.flag_key,
        enabled=flag.enabled,
        config=flag.config,
    )
