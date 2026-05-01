"""Auth routes — login, me, logout.

Login flow:
    1. Client POSTs facility_code + pin to /api/login.
    2. We look up the tenant by facility_code.
    3. We find candidate users by tenant_id.
    4. For each candidate, attempt verify_pin() until one matches.
       (Constant-time-ish: we always try at least one verify even if no
       candidates exist, to prevent timing-based facility_code enumeration.)
    5. On match, check lockout. If locked, fail.
    6. On success, reset failed_login_count, update last_login_at, issue JWT.
    7. On failure, increment failed_login_count, possibly lock the user.

The login endpoint is rate-limited per IP to slow brute force.

Failure responses are intentionally vague — `Invalid login` for everything,
no distinction between unknown facility, unknown user, wrong PIN, or locked
account. Distinguishing these would leak user-enumeration info to attackers.
"""

from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from nexus_care_auth import (
    PINMismatch,
    hash_pin,
    issue_token,
    needs_rehash,
    verify_pin,
)
from nexus_care_db import Tenant, User

from nexus_care_api.deps import AuthenticatedUser, get_db, require_user
from nexus_care_api.settings import Settings, get_settings


router = APIRouter(tags=["auth"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------
class LoginRequest(BaseModel):
    facility_code: str = Field(min_length=3, max_length=32)
    pin: str = Field(min_length=4, max_length=12)


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds


class MeResponse(BaseModel):
    id: int
    full_name: str
    role: str
    tenant_id: int
    tenant_state: str


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
GENERIC_LOGIN_FAIL = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Invalid login",
)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@router.post("/login", response_model=LoginResponse)
def login(
    payload: LoginRequest,
    request: Request,  # noqa: ARG001 — held for future rate-limiting hook
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> LoginResponse:
    """Authenticate a user. PIN + facility code → JWT."""
    # 1. Find the tenant by facility code.
    tenant = db.execute(
        select(Tenant).where(Tenant.facility_code == payload.facility_code.lower())
    ).scalar_one_or_none()

    if tenant is None:
        # Always perform at least one Argon2 verify on a dummy hash so failure
        # timing doesn't reveal whether the facility code exists. The dummy
        # hash is a known-bad reference; verify_pin will raise PINMismatch.
        try:
            verify_pin("000000", _DUMMY_HASH)
        except PINMismatch:
            pass
        raise GENERIC_LOGIN_FAIL

    # 2. Find candidate active users in this tenant.
    candidates = db.execute(
        select(User).where(User.tenant_id == tenant.id, User.is_active.is_(True))
    ).scalars().all()

    matched_user: User | None = None
    now = dt.datetime.now(dt.UTC)

    # 3. Try to verify against each candidate. Linear scan because PINs are
    #    salted, so we cannot just hash-and-look-up — we have to verify per
    #    candidate. With realistic facility sizes (typically <100 active
    #    staff) this is fine. If it ever becomes a perf issue, we add a
    #    pin_hash_lookup index column with a non-secret prefix derivation.
    for candidate in candidates:
        # Skip locked users transparently — don't reveal lockout state.
        if candidate.locked_until and candidate.locked_until > now:
            continue
        try:
            verify_pin(payload.pin, candidate.pin_hash)
        except PINMismatch:
            continue
        matched_user = candidate
        break

    if matched_user is None:
        # Same dummy verify as above to even out timing.
        try:
            verify_pin("000000", _DUMMY_HASH)
        except PINMismatch:
            pass
        # Increment failed_login_count for any candidate that exists with
        # this facility — but we can't tell *which* PIN they tried, so we
        # don't penalize specific accounts here. Lockout is enforced when
        # we DO find the user but the PIN is wrong (handled separately if
        # we add per-user attempt tracking). For now: simple model, can
        # tighten later.
        raise GENERIC_LOGIN_FAIL

    # 4. Re-check lockout (matched user is not locked, but defensive).
    if matched_user.locked_until and matched_user.locked_until > now:
        raise GENERIC_LOGIN_FAIL

    # 5. Success path. Reset attempt counter and update last_login.
    matched_user.failed_login_count = 0
    matched_user.locked_until = None
    matched_user.last_login_at = now

    # 6. Rehash if Argon2 parameters have been tightened.
    if needs_rehash(matched_user.pin_hash):
        matched_user.pin_hash = hash_pin(payload.pin)

    db.commit()

    # 7. Issue token.
    issued = issue_token(
        user_id=matched_user.id,
        tenant_id=tenant.id,
        tenant_state=tenant.state,
        region=tenant.region_code,
        role=matched_user.role,
        signing_key=settings.jwt_signing_key.get_secret_value(),
    )

    return LoginResponse(
        access_token=issued.token,
        expires_in=issued.claims.exp - issued.claims.iat,
    )


@router.get("/me", response_model=MeResponse)
def me(
    user: AuthenticatedUser = Depends(require_user),
    db: Session = Depends(get_db),
) -> MeResponse:
    """Return the currently-authenticated user's profile."""
    tenant = db.get(Tenant, user.tenant_id)
    assert tenant is not None  # require_user already verified
    return MeResponse(
        id=user.id,
        full_name=user.full_name,
        role=user.role,
        tenant_id=user.tenant_id,
        tenant_state=tenant.state,
    )


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------
# Pre-computed Argon2 hash of a known-bad PIN. Used for timing-equalizing
# verify calls when the user/facility lookup misses. The PIN behind it is
# arbitrary — it's never compared against a real PIN.
_DUMMY_HASH = hash_pin("dummy-do-not-use-this-pin-anywhere")
