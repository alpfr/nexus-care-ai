"""Clinical-feature integration tests for tranche 6a.

Covers:
  - Cross-tenant isolation on residents, medications, medication orders
  - PHI write guard (sandbox tenant cannot write residents/orders)
  - Room/bed uniqueness within active residents in a tenant
  - Formulary uniqueness (same drug + strength can't be added twice per tenant)
  - Witness flag auto-set for Schedule II-V controlled meds
  - Order state-machine: legal vs illegal transitions
  - Audit log entries get created on PHI writes

These are full-stack tests — they hit FastAPI route handlers and a real
Postgres. Run via `make test` after `make db-up`.
"""

from __future__ import annotations

import datetime as dt
import os
import secrets

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from nexus_care_auth import hash_pin
from nexus_care_db import AuditLog, Medication, MedicationOrder, Resident, Tenant, User
from nexus_care_db.session import make_engine, make_session_factory, session_scope

from nexus_care_api.app import create_app


pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Fixtures (shared with other integration tests; duplicated here for self-
# containment so this file can run alone)
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
def client():
    return TestClient(create_app())


def _unique_facility_code(prefix: str) -> str:
    return f"{prefix}-{secrets.token_hex(4)}"


def _make_tenant(
    db, *, name: str, facility_code: str, state: str = "active"
) -> Tenant:
    tenant = Tenant(name=name, facility_code=facility_code, state=state)
    db.add(tenant)
    db.flush()
    return tenant


def _make_user(
    db, *, tenant_id: int, full_name: str, role: str, pin: str
) -> User:
    user = User(
        tenant_id=tenant_id,
        full_name=full_name,
        role=role,
        pin_hash=hash_pin(pin),
        pin_hash_lookup=secrets.token_hex(16),
        is_active=True,
    )
    db.add(user)
    db.flush()
    return user


def _login(client: TestClient, facility_code: str, pin: str) -> str:
    resp = client.post(
        "/api/login",
        json={"facility_code": facility_code, "pin": pin},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


# ---------------------------------------------------------------------------
# Setup helpers
# ---------------------------------------------------------------------------
@pytest.fixture
def two_tenants_with_supervisors(session_factory):
    """Create two active tenants, each with a supervisor user."""
    code_a = _unique_facility_code("clin-a")
    code_b = _unique_facility_code("clin-b")
    pin_a = "111222"
    pin_b = "333444"

    with session_scope(session_factory) as db:
        ta = _make_tenant(db, name="Facility A", facility_code=code_a)
        tb = _make_tenant(db, name="Facility B", facility_code=code_b)
        _make_user(
            db,
            tenant_id=ta.id,
            full_name="Supervisor A",
            role="supervisor",
            pin=pin_a,
        )
        _make_user(
            db,
            tenant_id=tb.id,
            full_name="Supervisor B",
            role="supervisor",
            pin=pin_b,
        )
    return {
        "tenant_a": code_a,
        "tenant_b": code_b,
        "pin_a": pin_a,
        "pin_b": pin_b,
    }


@pytest.fixture
def sandbox_tenant_with_supervisor(session_factory):
    """A tenant in sandbox state — PHI writes should be blocked."""
    code = _unique_facility_code("clin-sandbox")
    pin = "555666"
    with session_scope(session_factory) as db:
        t = _make_tenant(
            db,
            name="Sandbox Co",
            facility_code=code,
            state="sandbox",
        )
        _make_user(
            db,
            tenant_id=t.id,
            full_name="Sandbox Supervisor",
            role="supervisor",
            pin=pin,
        )
    return {"facility_code": code, "pin": pin}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
def _admit_payload(**overrides):
    base = {
        "legal_first_name": "Test",
        "legal_last_name": "Person",
        "date_of_birth": "1950-01-15",
        "admission_date": dt.date.today().isoformat(),
        "code_status": "unknown",
        "fall_risk": "unassessed",
    }
    base.update(overrides)
    return base


class TestResidentIsolation:
    def test_residents_are_scoped_to_tenant(
        self, client, two_tenants_with_supervisors
    ):
        ctx = two_tenants_with_supervisors
        token_a = _login(client, ctx["tenant_a"], ctx["pin_a"])
        token_b = _login(client, ctx["tenant_b"], ctx["pin_b"])

        # Tenant A admits a resident.
        resp = client.post(
            "/api/residents",
            json=_admit_payload(legal_last_name="Alpha"),
            headers={"Authorization": f"Bearer {token_a}"},
        )
        assert resp.status_code == 201, resp.text
        resident_a_id = resp.json()["id"]

        # Tenant B cannot see it in list view.
        resp = client.get(
            "/api/residents",
            headers={"Authorization": f"Bearer {token_b}"},
        )
        assert resp.status_code == 200
        ids = [r["id"] for r in resp.json()]
        assert resident_a_id not in ids

        # Tenant B cannot fetch it directly — gets 404, not 403, so they
        # can't even probe for existence.
        resp = client.get(
            f"/api/residents/{resident_a_id}",
            headers={"Authorization": f"Bearer {token_b}"},
        )
        assert resp.status_code == 404

        # Tenant B cannot patch it.
        resp = client.patch(
            f"/api/residents/{resident_a_id}",
            json={"chart_note": "leaked"},
            headers={"Authorization": f"Bearer {token_b}"},
        )
        assert resp.status_code == 404


class TestPHIWriteGuard:
    def test_sandbox_tenant_cannot_admit_residents(
        self, client, sandbox_tenant_with_supervisor
    ):
        ctx = sandbox_tenant_with_supervisor
        token = _login(client, ctx["facility_code"], ctx["pin"])

        resp = client.post(
            "/api/residents",
            json=_admit_payload(),
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403
        body = resp.json()
        assert "PHI writes are not permitted" in body["detail"]

    def test_sandbox_tenant_can_still_populate_formulary(
        self, client, sandbox_tenant_with_supervisor
    ):
        """Medication catalog is not PHI — sandbox CAN populate it.
        This is intentional: the demo experience needs a formulary to
        write orders against."""
        ctx = sandbox_tenant_with_supervisor
        token = _login(client, ctx["facility_code"], ctx["pin"])

        resp = client.post(
            "/api/medications",
            json={
                "name": "Sandbox Drug",
                "strength": "10 mg",
                "form": "tablet",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 201, resp.text


class TestRoomBedUniqueness:
    def test_two_residents_cannot_share_a_bed(
        self, client, two_tenants_with_supervisors
    ):
        ctx = two_tenants_with_supervisors
        token = _login(client, ctx["tenant_a"], ctx["pin_a"])

        # First resident takes 101-A.
        resp = client.post(
            "/api/residents",
            json=_admit_payload(
                legal_last_name="Alpha", room="101", bed="A"
            ),
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 201

        # Second resident attempting 101-A is rejected.
        resp = client.post(
            "/api/residents",
            json=_admit_payload(
                legal_last_name="Beta", room="101", bed="A"
            ),
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 409
        assert "already occupied" in resp.json()["detail"].lower()

    def test_same_bed_in_a_different_tenant_is_fine(
        self, client, two_tenants_with_supervisors
    ):
        ctx = two_tenants_with_supervisors
        token_a = _login(client, ctx["tenant_a"], ctx["pin_a"])
        token_b = _login(client, ctx["tenant_b"], ctx["pin_b"])

        # 102-B in tenant A.
        client.post(
            "/api/residents",
            json=_admit_payload(legal_last_name="Alpha", room="102", bed="B"),
            headers={"Authorization": f"Bearer {token_a}"},
        ).raise_for_status()

        # 102-B in tenant B is fine — different building.
        resp = client.post(
            "/api/residents",
            json=_admit_payload(legal_last_name="Beta", room="102", bed="B"),
            headers={"Authorization": f"Bearer {token_b}"},
        )
        assert resp.status_code == 201


class TestFormularyUniqueness:
    def test_duplicate_drug_at_same_strength_rejected(
        self, client, two_tenants_with_supervisors
    ):
        ctx = two_tenants_with_supervisors
        token = _login(client, ctx["tenant_a"], ctx["pin_a"])

        client.post(
            "/api/medications",
            json={"name": "Aspirin", "strength": "81 mg", "form": "tablet"},
            headers={"Authorization": f"Bearer {token}"},
        ).raise_for_status()

        resp = client.post(
            "/api/medications",
            json={"name": "Aspirin", "strength": "81 mg", "form": "tablet"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 409
        assert "already in the formulary" in resp.json()["detail"].lower()

    def test_same_drug_different_strength_allowed(
        self, client, two_tenants_with_supervisors
    ):
        ctx = two_tenants_with_supervisors
        token = _login(client, ctx["tenant_a"], ctx["pin_a"])

        for strength in ("325 mg", "500 mg"):
            resp = client.post(
                "/api/medications",
                json={
                    "name": "Acetaminophen",
                    "strength": strength,
                    "form": "tablet",
                },
                headers={"Authorization": f"Bearer {token}"},
            )
            assert resp.status_code == 201


class TestWitnessFlagAutoSet:
    def test_controlled_substance_auto_flags_witness_required(
        self, client, two_tenants_with_supervisors
    ):
        ctx = two_tenants_with_supervisors
        token = _login(client, ctx["tenant_a"], ctx["pin_a"])

        # Add a Schedule II med.
        med_resp = client.post(
            "/api/medications",
            json={
                "name": "Hydromorphone",
                "strength": "2 mg",
                "form": "tablet",
                "schedule": "II",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        med_resp.raise_for_status()
        med_id = med_resp.json()["id"]

        # Admit a resident.
        resident_resp = client.post(
            "/api/residents",
            json=_admit_payload(legal_last_name="Quinn"),
            headers={"Authorization": f"Bearer {token}"},
        )
        resident_resp.raise_for_status()
        resident_id = resident_resp.json()["id"]

        # Write an order — witness_required should be set automatically.
        order_resp = client.post(
            f"/api/residents/{resident_id}/medication-orders",
            json={
                "medication_id": med_id,
                "dose": "2 mg",
                "route": "oral",
                "frequency": "Q4H PRN",
                "is_prn": True,
                "prn_indication": "Severe pain",
                "indication": "Post-op pain",
                "prescriber_name": "Dr. Test",
                "start_date": dt.date.today().isoformat(),
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert order_resp.status_code == 201, order_resp.text
        assert order_resp.json()["witness_required"] is True

    def test_uncontrolled_drug_does_not_flag_witness(
        self, client, two_tenants_with_supervisors
    ):
        ctx = two_tenants_with_supervisors
        token = _login(client, ctx["tenant_a"], ctx["pin_a"])

        med_resp = client.post(
            "/api/medications",
            json={"name": "Vitamin D3", "strength": "1000 IU", "form": "tablet"},
            headers={"Authorization": f"Bearer {token}"},
        )
        med_resp.raise_for_status()
        med_id = med_resp.json()["id"]

        resident_resp = client.post(
            "/api/residents",
            json=_admit_payload(legal_last_name="Reyes"),
            headers={"Authorization": f"Bearer {token}"},
        )
        resident_resp.raise_for_status()
        resident_id = resident_resp.json()["id"]

        order_resp = client.post(
            f"/api/residents/{resident_id}/medication-orders",
            json={
                "medication_id": med_id,
                "dose": "1000 IU",
                "route": "oral",
                "frequency": "Daily",
                "indication": "Vitamin D deficiency",
                "prescriber_name": "Dr. Test",
                "start_date": dt.date.today().isoformat(),
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert order_resp.status_code == 201
        assert order_resp.json()["witness_required"] is False


class TestOrderStateMachine:
    def _make_active_order(self, client, token: str) -> int:
        med_resp = client.post(
            "/api/medications",
            json={"name": "Loratadine", "strength": "10 mg", "form": "tablet"},
            headers={"Authorization": f"Bearer {token}"},
        )
        med_resp.raise_for_status()
        med_id = med_resp.json()["id"]

        r_resp = client.post(
            "/api/residents",
            json=_admit_payload(legal_last_name="Singh"),
            headers={"Authorization": f"Bearer {token}"},
        )
        r_resp.raise_for_status()
        r_id = r_resp.json()["id"]

        o_resp = client.post(
            f"/api/residents/{r_id}/medication-orders",
            json={
                "medication_id": med_id,
                "dose": "10 mg",
                "route": "oral",
                "frequency": "Daily",
                "indication": "Allergic rhinitis",
                "prescriber_name": "Dr. Test",
                "start_date": dt.date.today().isoformat(),
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        o_resp.raise_for_status()
        return o_resp.json()["id"]

    def test_active_to_held_with_reason_succeeds(
        self, client, two_tenants_with_supervisors
    ):
        ctx = two_tenants_with_supervisors
        token = _login(client, ctx["tenant_a"], ctx["pin_a"])
        order_id = self._make_active_order(client, token)

        resp = client.post(
            f"/api/medication-orders/{order_id}/transition",
            json={"target_status": "held", "reason": "NPO before procedure"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "held"
        assert resp.json()["status_reason"] == "NPO before procedure"

    def test_held_without_reason_rejected(
        self, client, two_tenants_with_supervisors
    ):
        ctx = two_tenants_with_supervisors
        token = _login(client, ctx["tenant_a"], ctx["pin_a"])
        order_id = self._make_active_order(client, token)

        resp = client.post(
            f"/api/medication-orders/{order_id}/transition",
            json={"target_status": "held"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 422
        assert "reason is required" in resp.json()["detail"].lower()

    def test_discontinued_to_active_is_illegal(
        self, client, two_tenants_with_supervisors
    ):
        ctx = two_tenants_with_supervisors
        token = _login(client, ctx["tenant_a"], ctx["pin_a"])
        order_id = self._make_active_order(client, token)

        client.post(
            f"/api/medication-orders/{order_id}/transition",
            json={"target_status": "discontinued", "reason": "Pt refused"},
            headers={"Authorization": f"Bearer {token}"},
        ).raise_for_status()

        resp = client.post(
            f"/api/medication-orders/{order_id}/transition",
            json={"target_status": "active"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 409
        assert "illegal transition" in resp.json()["detail"].lower()


class TestAuditLogging:
    def test_admit_records_audit_entry(
        self, client, two_tenants_with_supervisors, session_factory
    ):
        ctx = two_tenants_with_supervisors
        token = _login(client, ctx["tenant_a"], ctx["pin_a"])

        resp = client.post(
            "/api/residents",
            json=_admit_payload(legal_last_name="Audited"),
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 201
        resident_id = resp.json()["id"]

        with session_scope(session_factory) as db:
            entries = (
                db.execute(
                    select(AuditLog).where(
                        AuditLog.entity_type == "resident",
                        AuditLog.entity_id == str(resident_id),
                    )
                )
                .scalars()
                .all()
            )
            assert len(entries) >= 1
            assert any(e.action == "create" for e in entries)
