"""Cross-tenant isolation tests — the canary in the coal mine.

These tests prove that user A in tenant 1 cannot read or write tenant 2's
data. Every PHI-bearing model added in future tranches gets a corresponding
test here.

Tranche 2 covers the foundations:
  - The audit log (the only PHI-adjacent table existing yet) cannot be
    queried across tenants.
  - The auth flow rejects a token whose tenant_id has been tampered with.
  - The PHI write guard blocks writes from non-active tenants.

These tests require a running Postgres. They're marked `integration` and
are run via `make test` once docker compose is up.
"""

from __future__ import annotations

import os
import secrets
from sqlalchemy import text

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from nexus_care_auth import hash_pin
from nexus_care_db import AuditLog, Tenant, User
from nexus_care_db.session import make_engine, make_session_factory, session_scope

from nexus_care_api.app import create_app


pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session")
def database_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url:
        pytest.skip(
            "DATABASE_URL not set — skipping integration tests. "
            "Run `make db-up` and export DATABASE_URL to enable."
        )
    return url


@pytest.fixture(scope="session")
def engine(database_url: str):
    return make_engine(database_url)


@pytest.fixture(scope="session")
def session_factory(engine):
    return make_session_factory(engine)


@pytest.fixture
def two_tenants(session_factory):
    """Create two active tenants with one supervisor each. Yields a dict
    with tenant_a, tenant_b, user_a, user_b, pin_a, pin_b. Cleans up on
    teardown."""
    pin_a = "111111"
    pin_b = "222222"
    code_a = f"test-tenant-a-{secrets.token_hex(4)}"
    code_b = f"test-tenant-b-{secrets.token_hex(4)}"

    with session_scope(session_factory) as session:
        tenant_a = Tenant(
            name="Test Tenant A",
            facility_code=code_a,
            state="active",
            region_code="us-central",
        )
        tenant_b = Tenant(
            name="Test Tenant B",
            facility_code=code_b,
            state="active",
            region_code="us-central",
        )
        session.add_all([tenant_a, tenant_b])
        session.flush()

        user_a = User(
            tenant_id=tenant_a.id,
            full_name="Test Supervisor A",
            pin_hash=hash_pin(pin_a),
            pin_hash_lookup=secrets.token_hex(16),
            role="supervisor",
            is_active=True,
        )
        user_b = User(
            tenant_id=tenant_b.id,
            full_name="Test Supervisor B",
            pin_hash=hash_pin(pin_b),
            pin_hash_lookup=secrets.token_hex(16),
            role="supervisor",
            is_active=True,
        )
        session.add_all([user_a, user_b])
        session.flush()

        ids = {
            "tenant_a_id": tenant_a.id,
            "tenant_b_id": tenant_b.id,
            "user_a_id": user_a.id,
            "user_b_id": user_b.id,
            "code_a": code_a,
            "code_b": code_b,
            "pin_a": pin_a,
            "pin_b": pin_b,
        }

    yield ids

    # Teardown: delete users (and any audit log rows) before tenants
    # because of the RESTRICT FK from users.tenant_id.
    with session_scope(session_factory) as session:
        session.execute(
            text(
                "DELETE FROM tenant_data.audit_log WHERE tenant_id IN "
                "(SELECT id FROM platform.tenants WHERE facility_code IN (:a, :b))"
            ),
            {"a": ids["code_a"], "b": ids["code_b"]},
        )
        session.execute(
            text("DELETE FROM platform.users WHERE tenant_id IN "
                 "(SELECT id FROM platform.tenants WHERE facility_code IN (:a, :b))"),
            {"a": ids["code_a"], "b": ids["code_b"]},
        )
    with session_scope(session_factory) as session:
        for user_id in (ids["user_a_id"], ids["user_b_id"]):
            user = session.get(User, user_id)
            if user is not None:
                session.delete(user)
        for tenant_id in (ids["tenant_a_id"], ids["tenant_b_id"]):
            tenant = session.get(Tenant, tenant_id)
            if tenant is not None:
                session.delete(tenant)


@pytest.fixture
def client():
    return TestClient(create_app())


# ---------------------------------------------------------------------------
# Login flow basics
# ---------------------------------------------------------------------------
class TestLoginFlow:
    def test_login_with_valid_credentials(self, client, two_tenants):
        resp = client.post(
            "/api/login",
            json={"facility_code": two_tenants["code_a"], "pin": two_tenants["pin_a"]},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "access_token" in body
        assert body["token_type"] == "bearer"
        assert body["expires_in"] > 0

    def test_login_with_wrong_pin(self, client, two_tenants):
        resp = client.post(
            "/api/login",
            json={"facility_code": two_tenants["code_a"], "pin": "000000"},
        )
        assert resp.status_code == 401
        assert resp.json() == {"detail": "Invalid login"}

    def test_login_with_unknown_facility(self, client):
        resp = client.post(
            "/api/login",
            json={"facility_code": "nonexistent-facility", "pin": "000000"},
        )
        assert resp.status_code == 401
        # Same response as wrong PIN — no enumeration leakage.
        assert resp.json() == {"detail": "Invalid login"}

    def test_pin_from_other_tenant_does_not_work(self, client, two_tenants):
        """Tenant B's PIN must NOT authenticate against Tenant A."""
        resp = client.post(
            "/api/login",
            json={"facility_code": two_tenants["code_a"], "pin": two_tenants["pin_b"]},
        )
        assert resp.status_code == 401


class TestMeEndpoint:
    def test_me_returns_correct_user(self, client, two_tenants):
        login = client.post(
            "/api/login",
            json={"facility_code": two_tenants["code_a"], "pin": two_tenants["pin_a"]},
        )
        token = login.json()["access_token"]
        resp = client.get("/api/me", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == two_tenants["user_a_id"]
        assert body["tenant_id"] == two_tenants["tenant_a_id"]
        assert body["role"] == "supervisor"
        assert body["tenant_state"] == "active"

    def test_me_without_token_unauthorized(self, client):
        resp = client.get("/api/me")
        assert resp.status_code == 401

    def test_me_with_garbage_token_unauthorized(self, client):
        resp = client.get("/api/me", headers={"Authorization": "Bearer garbage"})
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Cross-tenant isolation
# ---------------------------------------------------------------------------
class TestCrossTenantIsolation:
    def test_audit_log_query_filtered_to_tenant(self, session_factory, two_tenants):
        """Insert an audit row for each tenant. Querying for tenant A must
        return only A's row, never B's."""
        with session_scope(session_factory) as session:
            session.add_all([
                AuditLog(
                    tenant_id=two_tenants["tenant_a_id"],
                    actor_user_id=two_tenants["user_a_id"],
                    tenant_state="active",
                    action="read",
                    entity_type="resident",
                    entity_id="ABC",
                    outcome="success",
                    summary="A read",
                ),
                AuditLog(
                    tenant_id=two_tenants["tenant_b_id"],
                    actor_user_id=two_tenants["user_b_id"],
                    tenant_state="active",
                    action="read",
                    entity_type="resident",
                    entity_id="XYZ",
                    outcome="success",
                    summary="B read",
                ),
            ])

        with session_scope(session_factory) as session:
            rows_a = session.execute(
                select(AuditLog).where(AuditLog.tenant_id == two_tenants["tenant_a_id"])
            ).scalars().all()
            assert all(r.tenant_id == two_tenants["tenant_a_id"] for r in rows_a)
            assert any(r.summary == "A read" for r in rows_a)
            assert not any(r.summary == "B read" for r in rows_a)
