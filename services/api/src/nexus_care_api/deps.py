"""FastAPI dependencies — DB session, auth, tenant context.

These are the primitives every route handler imports. They wire up the
plumbing once so handlers stay focused on business logic.

    @router.get("/me")
    def me(user: AuthenticatedUser = Depends(require_user)) -> Schema:
        ...

The `require_user` dependency:
  1. Pulls the Bearer token out of the Authorization header.
  2. Verifies the JWT signature and claims.
  3. Loads the user from the database.
  4. Checks tokens_invalid_after for revocation.
  5. Sets the tenant context for the request.
  6. Returns the user.

Anything downstream that needs the user just `Depends(require_user)`.
Anything that needs only the tenant context can use `Depends(require_tenant)`.
"""

from __future__ import annotations

from collections.abc import Generator
from dataclasses import dataclass
from functools import lru_cache

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session, sessionmaker

from nexus_care_auth import InvalidTokenError, verify_token
from nexus_care_db import Tenant, User
from nexus_care_db.session import make_engine, make_session_factory
from nexus_care_tenancy import (
    TenantContext,
    TenantState,
    clear_tenant_context,
    current_tenant,
    set_tenant_context,
)

from nexus_care_api.settings import Settings, get_settings


# ---------------------------------------------------------------------------
# Database session
# ---------------------------------------------------------------------------
@lru_cache(maxsize=1)
def _get_session_factory() -> sessionmaker[Session]:
    """One engine, one factory, lazily initialized on first request."""
    settings = get_settings()
    engine = make_engine(
        settings.database_url.get_secret_value(),
        echo=settings.sql_echo,
    )
    return make_session_factory(engine)


def get_db() -> Generator[Session, None, None]:
    """Yield a request-scoped DB session. Closed automatically when the
    request handler returns."""
    factory = _get_session_factory()
    session = factory()
    try:
        yield session
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class AuthenticatedUser:
    id: int
    tenant_id: int
    role: str
    full_name: str


def _extract_bearer(authorization: str | None) -> str:
    """Pull the JWT out of an Authorization header. Returns the token only;
    raises 401 on anything malformed."""
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return parts[1]


async def require_user(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> AuthenticatedUser:
    """Require a valid bearer token. Loads the user from the DB, checks
    revocation, and sets the tenant context for the request.

    Raises 401 on any auth failure with a generic message — we never
    distinguish 'no such user' from 'bad token' from 'revoked' to clients.
    """
    token = _extract_bearer(authorization)

    # First decode without revocation check — we need claims.sub to look
    # up the user before we know their tokens_invalid_after value.
    try:
        claims = verify_token(token, signing_key=settings.jwt_signing_key.get_secret_value())
    except InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None

    user = db.get(User, int(claims.sub))
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Now verify with the revocation check.
    try:
        verify_token(
            token,
            signing_key=settings.jwt_signing_key.get_secret_value(),
            tokens_invalid_after=user.tokens_invalid_after,
        )
    except InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None

    # Look up the tenant for region + state.
    tenant = db.get(Tenant, user.tenant_id)
    if tenant is None:
        # User row references a deleted tenant — should never happen given
        # the FK with ON DELETE RESTRICT, but fail closed.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    set_tenant_context(
        tenant_id=tenant.id,
        state=TenantState(tenant.state),
        region_code=tenant.region_code,
    )

    return AuthenticatedUser(
        id=user.id,
        tenant_id=user.tenant_id,
        role=user.role,
        full_name=user.full_name,
    )


def require_tenant(
    _user: AuthenticatedUser = Depends(require_user),
) -> TenantContext:
    """Convenience dep when a handler needs the tenant context but not the
    full user object. Going through require_user ensures the tenant context
    has actually been set."""
    return current_tenant()


# ---------------------------------------------------------------------------
# Cleanup hook
# ---------------------------------------------------------------------------
def reset_tenant_context_after_request() -> Generator[None, None, None]:
    """Use as a `dependency` on routers to clear the tenant context after the
    response is produced. Belt-and-suspenders — context vars in asyncio are
    task-local already, but explicit cleanup avoids any surprise leakage if
    a future change moves work outside the request task."""
    try:
        yield
    finally:
        clear_tenant_context()
