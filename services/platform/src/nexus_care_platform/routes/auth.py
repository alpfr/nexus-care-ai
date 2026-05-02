"""Platform-admin auth routes."""

from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from nexus_care_auth import (
    PasswordMismatch,
    hash_password,
    issue_token,
    password_needs_rehash,
    verify_password,
)
from nexus_care_db import PlatformAdmin

from nexus_care_platform.deps import AuthenticatedAdmin, get_db, require_admin
from nexus_care_platform.settings import Settings, get_settings

router = APIRouter(tags=["platform-auth"])


class AdminLoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=256)


class AdminLoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class AdminMeResponse(BaseModel):
    id: int
    email: str
    full_name: str


GENERIC_LOGIN_FAIL = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Invalid login",
)


@router.post("/admin/login", response_model=AdminLoginResponse)
def admin_login(
    payload: AdminLoginRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> AdminLoginResponse:
    admin = db.execute(
        select(PlatformAdmin).where(PlatformAdmin.email == payload.email.lower())
    ).scalar_one_or_none()

    now = dt.datetime.now(dt.UTC)

    if admin is None:
        # Burn an Argon2 verify on the dummy hash so failure timing doesn't
        # reveal whether the email exists.
        try:
            verify_password("dummy", _DUMMY_HASH)
        except PasswordMismatch:
            pass
        raise GENERIC_LOGIN_FAIL

    if not admin.is_active:
        raise GENERIC_LOGIN_FAIL

    if admin.locked_until and admin.locked_until > now:
        raise GENERIC_LOGIN_FAIL

    try:
        verify_password(payload.password, admin.password_hash)
    except PasswordMismatch:
        admin.failed_login_count += 1
        if admin.failed_login_count >= settings.failed_login_lock_threshold:
            admin.locked_until = now + dt.timedelta(
                minutes=settings.lockout_minutes
            )
        db.commit()
        raise GENERIC_LOGIN_FAIL from None

    # Success.
    admin.failed_login_count = 0
    admin.locked_until = None
    admin.last_login_at = now

    if password_needs_rehash(admin.password_hash):
        admin.password_hash = hash_password(payload.password)

    db.commit()

    issued = issue_token(
        user_id=admin.id,
        tenant_id=0,  # platform admins are not tenant-scoped
        tenant_state="active",  # n/a for admins; required by claims schema
        region="global",
        role="platform_admin",
        signing_key=settings.jwt_signing_key.get_secret_value(),
    )

    return AdminLoginResponse(
        access_token=issued.token,
        expires_in=issued.claims.exp - issued.claims.iat,
    )


@router.get("/admin/me", response_model=AdminMeResponse)
def admin_me(
    admin: AuthenticatedAdmin = Depends(require_admin),
) -> AdminMeResponse:
    return AdminMeResponse(
        id=admin.id,
        email=admin.email,
        full_name=admin.full_name,
    )


# Pre-computed Argon2 hash for timing-equalization on missing-email lookups.
_DUMMY_HASH = hash_password("dummy-do-not-use-this-password-anywhere")
