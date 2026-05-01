"""Seed a local-dev database with a sandbox tenant and one supervisor user.

Run from repo root after `alembic upgrade head`:

    uv run python scripts/seed_sandbox.py

Idempotent — running it twice is safe; existing rows are skipped.
"""

from __future__ import annotations

import os
import secrets
import sys

from sqlalchemy import select

from nexus_care_auth import hash_pin
from nexus_care_db import Tenant, User
from nexus_care_db.session import make_engine, make_session_factory, session_scope


SANDBOX_FACILITY_CODE = "demo-sandbox"
SANDBOX_FACILITY_NAME = "Demo Sandbox Facility"

SUPERVISOR_NAME = "Demo Supervisor"
SUPERVISOR_PIN = "246810"
SUPERVISOR_ROLE = "supervisor"


def main() -> int:
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print(
            "DATABASE_URL is not set. Export it first:\n"
            "  export DATABASE_URL='postgresql+psycopg://nexus:nexus@localhost:5433/nexus_care'",
            file=sys.stderr,
        )
        return 1

    engine = make_engine(database_url)
    factory = make_session_factory(engine)

    with session_scope(factory) as session:
        # --- Tenant ---
        tenant = session.execute(
            select(Tenant).where(Tenant.facility_code == SANDBOX_FACILITY_CODE)
        ).scalar_one_or_none()

        if tenant is None:
            tenant = Tenant(
                name=SANDBOX_FACILITY_NAME,
                facility_code=SANDBOX_FACILITY_CODE,
                state="sandbox",
                region_code="us-central",
            )
            session.add(tenant)
            session.flush()
            print(f"Created tenant id={tenant.id} facility_code={tenant.facility_code}")
        else:
            print(
                f"Tenant already exists: id={tenant.id} "
                f"facility_code={tenant.facility_code} state={tenant.state}"
            )

        # --- Supervisor user ---
        existing_supervisor = session.execute(
            select(User).where(
                User.tenant_id == tenant.id, User.full_name == SUPERVISOR_NAME
            )
        ).scalar_one_or_none()

        if existing_supervisor is None:
            user = User(
                tenant_id=tenant.id,
                full_name=SUPERVISOR_NAME,
                pin_hash=hash_pin(SUPERVISOR_PIN),
                pin_hash_lookup=secrets.token_hex(16),
                role=SUPERVISOR_ROLE,
                is_active=True,
            )
            session.add(user)
            session.flush()
            print(f"Created user id={user.id} role={user.role}")
        else:
            print(f"Supervisor user already exists: id={existing_supervisor.id}")

    print()
    print("=" * 60)
    print(" Local sandbox is ready. Log in with:")
    print(f"   facility_code: {SANDBOX_FACILITY_CODE}")
    print(f"   pin:           {SUPERVISOR_PIN}")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
