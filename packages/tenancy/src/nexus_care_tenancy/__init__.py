"""Tenant scoping primitives.

Every service in Nexus Care AI uses these primitives to enforce that a request
acting on behalf of one tenant cannot read or write another tenant's data.

The pattern:

    1. Auth middleware resolves `tenant_id` from the JWT and the user's tenant
       state from the database.
    2. Middleware calls `set_tenant_context(tenant_id, state)`.
    3. All downstream code (route handlers, services, ORM queries) reads from
       `current_tenant_id()` via `Depends(require_tenant)` or directly.
    4. Write paths that touch PHI must call `assert_can_write_phi()` first.
       The state machine blocks PHI writes from non-`active` tenants.

Cross-tenant isolation is also enforced at the SQL layer (see scoped_query in
nexus_care_db) but this module is the canonical source of truth for "which
tenant are we acting on" and "is this tenant allowed to write PHI right now".
"""

from __future__ import annotations

import enum
from contextvars import ContextVar
from dataclasses import dataclass


class TenantState(enum.StrEnum):
    """Lifecycle state of a tenant.

    The state machine is documented in ARCHITECTURE.md. The critical invariant
    enforced here: PHI writes are only permitted when state == ACTIVE.
    """

    SANDBOX = "sandbox"
    PENDING_ACTIVATION = "pending_activation"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    TERMINATED = "terminated"


@dataclass(frozen=True, slots=True)
class TenantContext:
    """The tenant identity for the current request."""

    tenant_id: int
    state: TenantState
    region_code: str

    @property
    def can_write_phi(self) -> bool:
        """True if this tenant is permitted to write protected health information."""
        return self.state is TenantState.ACTIVE

    @property
    def is_readonly(self) -> bool:
        """True if writes of any kind should be blocked."""
        return self.state in {TenantState.SUSPENDED, TenantState.TERMINATED}


# The context var that carries the current tenant through a request. Each
# request handler sets it once, and every downstream layer reads it.
#
# We use ContextVar (not threading.local) because FastAPI runs handlers in a
# single asyncio loop — different requests share the same OS thread. ContextVar
# is task-local and survives `await`, which threading.local does not.
_tenant_ctx: ContextVar[TenantContext | None] = ContextVar("tenant_ctx", default=None)


class TenantNotSetError(RuntimeError):
    """Raised when code requires a tenant context but none is set.

    This is always a bug. It means a route handler ran without going through
    the tenant-resolving middleware, which means we cannot enforce isolation.
    Fail closed and loud.
    """


class PHIWriteForbiddenError(PermissionError):
    """Raised when code attempts to write PHI for a tenant that is not active.

    Sandbox / pending / suspended / terminated tenants must never produce PHI
    writes. This exception is the safety net at the application boundary; the
    same invariant is also enforced by audit triggers at the DB layer in
    later phases.
    """


def set_tenant_context(*, tenant_id: int, state: TenantState, region_code: str) -> TenantContext:
    """Set the tenant context for the current request. Called by middleware."""
    ctx = TenantContext(tenant_id=tenant_id, state=state, region_code=region_code)
    _tenant_ctx.set(ctx)
    return ctx


def clear_tenant_context() -> None:
    """Clear the tenant context. Called at end of request by middleware."""
    _tenant_ctx.set(None)


def current_tenant() -> TenantContext:
    """Return the active tenant context. Raises if none is set.

    Use this anywhere downstream of auth middleware that needs to know which
    tenant is acting. If it raises, an unauthenticated path slipped through
    your routing — fix the routing, do not catch this exception.
    """
    ctx = _tenant_ctx.get()
    if ctx is None:
        raise TenantNotSetError(
            "No tenant context set. This request did not go through tenant-resolving "
            "middleware. Verify the route is mounted under an authenticated router."
        )
    return ctx


def current_tenant_id() -> int:
    """Convenience: just the tenant_id."""
    return current_tenant().tenant_id


def assert_can_write_phi() -> None:
    """Guard for write paths that touch PHI.

    Call this at the top of any handler that creates / updates / deletes a row
    in a table containing protected health information (residents, medications,
    clinical notes, vital signs, etc.).

    Raises PHIWriteForbiddenError if the tenant is not in ACTIVE state.
    """
    ctx = current_tenant()
    if not ctx.can_write_phi:
        raise PHIWriteForbiddenError(
            f"Tenant {ctx.tenant_id} is in state {ctx.state.value!r}; "
            f"PHI writes require state {TenantState.ACTIVE.value!r}. "
            f"Activate the tenant via the platform service before retrying."
        )


def assert_can_write() -> None:
    """Guard for any write path (PHI or not).

    Less strict than assert_can_write_phi — sandbox tenants can write
    non-PHI data (e.g., user profile updates). Suspended and terminated
    tenants cannot write anything.
    """
    ctx = current_tenant()
    if ctx.is_readonly:
        raise PermissionError(
            f"Tenant {ctx.tenant_id} is in state {ctx.state.value!r}; writes are blocked."
        )


__all__ = [
    "PHIWriteForbiddenError",
    "TenantContext",
    "TenantNotSetError",
    "TenantState",
    "assert_can_write",
    "assert_can_write_phi",
    "clear_tenant_context",
    "current_tenant",
    "current_tenant_id",
    "set_tenant_context",
]
