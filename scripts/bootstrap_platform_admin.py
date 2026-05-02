"""Bootstrap a platform-admin account.

Usage:

    DATABASE_URL='...' uv run python scripts/bootstrap_platform_admin.py \\
        --email admin@example.com \\
        --name 'Platform Admin' \\
        --password 'change-me-in-real-life'

Idempotent — if an admin with that email already exists, prints info and
exits cleanly (the password is NOT updated; use a separate flow for that).
"""

from __future__ import annotations

import argparse
import os
import secrets
import sys

from sqlalchemy import select

from nexus_care_auth import hash_password
from nexus_care_db import PlatformAdmin
from nexus_care_db.session import make_engine, make_session_factory, session_scope


def main() -> int:
    parser = argparse.ArgumentParser(description="Bootstrap a Nexus Care platform admin.")
    parser.add_argument("--email", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument(
        "--password",
        default=None,
        help="If omitted, a random password is generated and printed once.",
    )
    args = parser.parse_args()

    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print(
            "DATABASE_URL is not set. Export it first.",
            file=sys.stderr,
        )
        return 1

    email = args.email.strip().lower()
    password = args.password or secrets.token_urlsafe(16)
    generated = args.password is None

    engine = make_engine(database_url)
    factory = make_session_factory(engine)

    with session_scope(factory) as session:
        existing = session.execute(
            select(PlatformAdmin).where(PlatformAdmin.email == email)
        ).scalar_one_or_none()

        if existing is not None:
            print(
                f"Platform admin already exists: id={existing.id} email={existing.email}\n"
                f"(No changes made. Use a separate flow to reset the password.)"
            )
            return 0

        admin = PlatformAdmin(
            email=email,
            full_name=args.name,
            password_hash=hash_password(password),
        )
        session.add(admin)
        session.flush()
        print(f"Created platform admin: id={admin.id} email={admin.email}")

    print()
    print("=" * 60)
    print(" Platform admin ready. Log in via:")
    print()
    print(f"   email:    {email}")
    if generated:
        print(f"   password: {password}    ← generated (save this NOW)")
    else:
        print("   password: <as supplied>")
    print()
    print(" curl example:")
    print("   curl -X POST http://localhost:18002/api/platform/admin/login \\")
    print("     -H 'Content-Type: application/json' \\")
    print(f"     -d '{{\"email\":\"{email}\",\"password\":\"{password}\"}}'")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
