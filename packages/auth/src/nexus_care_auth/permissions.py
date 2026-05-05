"""Authorization (permissions) for Nexus Care AI.

A single `can(user, action, resource)` helper is the only place in the codebase
that decides whether an action is permitted. Route handlers, services, and
background jobs call it; nobody bypasses it with raw role-string comparisons.

The model is RBAC for now: a user has one role per tenant; each role has a set
of permitted (action, resource_type) pairs. ABAC (per-resource ownership,
relationship-based grants) lands later if a customer demands it; the API
shape is designed so it's extensible.

Roles:
    nurse           — bedside clinical user. Can document, administer meds,
                      read assigned residents.
    med_tech        — medication administration only.
    caregiver       — non-clinical support. ADL documentation, vitals only.
    supervisor      — facility-level oversight. All clinical access for the
                      facility, plus audit log and staffing.
    tenant_admin    — facility administrator. Supervisor permissions plus
                      user management for the tenant.
    platform_admin  — Nexus Care AI staff. Tenant lifecycle (sandbox →
                      active), feature flags, billing. Not a clinical role —
                      cannot read PHI through these permissions.

Resources:
    'resident', 'medication', 'medication_order', 'med_pass',
    'clinical_note', 'soap_note', 'vital_sign', 'adl_assessment',
    'mds_assessment', 'care_plan', 'physician_order', 'consent',
    'incident_report', 'audit_log', 'user', 'tenant', 'feature_flag',
    'baa_artifact', 'identity_verification', 'subscription'

Actions:
    'read', 'create', 'update', 'delete', 'sign'
    (plus a few resource-specific ones like 'administer' for med_pass)
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol

# ---------------------------------------------------------------------------
# Permission tables
# ---------------------------------------------------------------------------
# Each entry is (action, resource). A '*' means any value of that field.
# Order matters — the first match wins. Negative permissions are not modeled
# here; if a role shouldn't do something, just don't list it.

_NURSE: frozenset[tuple[str, str]] = frozenset(
    {
        ("read", "resident"),
        ("update", "resident"),
        ("read", "medication"),
        ("read", "medication_order"),
        ("administer", "med_pass"),
        ("read", "med_pass"),
        ("create", "med_pass"),
        ("create", "clinical_note"),
        ("read", "clinical_note"),
        ("update", "clinical_note"),
        ("create", "soap_note"),
        ("read", "soap_note"),
        ("create", "vital_sign"),
        ("read", "vital_sign"),
        ("create", "adl_assessment"),
        ("read", "adl_assessment"),
        ("read", "care_plan"),
        ("read", "physician_order"),
        ("read", "consent"),
        ("create", "incident_report"),
        ("read", "incident_report"),
    }
)

_MED_TECH: frozenset[tuple[str, str]] = frozenset(
    {
        ("read", "resident"),
        ("read", "medication"),
        ("read", "medication_order"),
        ("administer", "med_pass"),
        ("create", "med_pass"),
        ("read", "med_pass"),
    }
)

_CAREGIVER: frozenset[tuple[str, str]] = frozenset(
    {
        ("read", "resident"),
        ("create", "vital_sign"),
        ("read", "vital_sign"),
        ("create", "adl_assessment"),
        ("read", "adl_assessment"),
        ("create", "incident_report"),
        ("read", "incident_report"),
    }
)

_SUPERVISOR: frozenset[tuple[str, str]] = frozenset(
    {
        *_NURSE,
        # plus oversight
        ("create", "mds_assessment"),
        ("read", "mds_assessment"),
        ("update", "mds_assessment"),
        ("sign", "mds_assessment"),
        ("create", "care_plan"),
        ("update", "care_plan"),
        ("read", "physician_order"),
        ("create", "consent"),
        ("update", "consent"),
        ("update", "incident_report"),
        ("read", "audit_log"),
        ("read", "user"),
    }
)

_TENANT_ADMIN: frozenset[tuple[str, str]] = frozenset(
    {
        *_SUPERVISOR,
        ("create", "user"),
        ("update", "user"),
        ("delete", "user"),
        ("read", "tenant"),
        ("update", "tenant"),
    }
)

_PLATFORM_ADMIN: frozenset[tuple[str, str]] = frozenset(
    {
        # Platform admins do NOT inherit clinical permissions. They cannot read
        # PHI through this helper — only manage tenants and platform-level data.
        ("read", "tenant"),
        ("create", "tenant"),
        ("update", "tenant"),
        ("delete", "tenant"),
        ("read", "feature_flag"),
        ("create", "feature_flag"),
        ("update", "feature_flag"),
        ("delete", "feature_flag"),
        ("read", "baa_artifact"),
        ("create", "baa_artifact"),
        ("read", "identity_verification"),
        ("update", "identity_verification"),
        ("read", "subscription"),
        ("update", "subscription"),
    }
)

_ROLE_PERMISSIONS: Mapping[str, frozenset[tuple[str, str]]] = {
    "nurse": _NURSE,
    "med_tech": _MED_TECH,
    "caregiver": _CAREGIVER,
    "supervisor": _SUPERVISOR,
    "tenant_admin": _TENANT_ADMIN,
    "platform_admin": _PLATFORM_ADMIN,
}


class _UserLike(Protocol):
    """Anything with a `role` attribute works. Lets `can()` be called with
    SQLAlchemy models, Pydantic models, or simple dataclasses without forcing
    a specific type.
    """

    role: str


def can(user: _UserLike, action: str, resource: str) -> bool:
    """Return True if `user` is permitted to perform `action` on `resource`.

    The user's tenant scope is NOT checked here — tenant scoping is enforced
    separately in the data layer (see nexus_care_tenancy). This helper only
    decides 'is the role allowed to do this kind of thing'.
    """
    permissions = _ROLE_PERMISSIONS.get(user.role)
    if permissions is None:
        return False
    return (action, resource) in permissions


__all__ = ["can"]
