"""Seed the demo sandbox tenant with a realistic LTC formulary and residents.

Idempotent — running it twice doesn't create duplicates. Looks for the
demo-sandbox tenant created by seed_sandbox.py and populates it.

Usage:
    uv run python scripts/seed_clinical_demo.py
"""

from __future__ import annotations

import datetime as dt
import os
import sys

from nexus_care_db import Medication, MedicationOrder, Resident, Tenant
from nexus_care_db.session import make_engine, make_session_factory, session_scope
from sqlalchemy import select
from sqlalchemy.orm import Session


def _ensure_med(
    db: Session,
    *,
    tenant_id: int,
    name: str,
    strength: str,
    form: str,
    schedule: str = "none",
    brand_name: str | None = None,
) -> Medication:
    """Get-or-create a Medication row with the given identity."""
    existing = db.execute(
        select(Medication).where(
            Medication.tenant_id == tenant_id,
            Medication.name == name,
            Medication.strength == strength,
        )
    ).scalar_one_or_none()
    if existing:
        return existing
    med = Medication(
        tenant_id=tenant_id,
        name=name,
        brand_name=brand_name,
        strength=strength,
        form=form,
        schedule=schedule,
    )
    db.add(med)
    db.flush()
    return med


def _ensure_resident(
    db: Session,
    *,
    tenant_id: int,
    legal_first_name: str,
    legal_last_name: str,
    **kwargs,
) -> Resident:
    existing = db.execute(
        select(Resident).where(
            Resident.tenant_id == tenant_id,
            Resident.legal_first_name == legal_first_name,
            Resident.legal_last_name == legal_last_name,
        )
    ).scalar_one_or_none()
    if existing:
        return existing
    resident = Resident(
        tenant_id=tenant_id,
        legal_first_name=legal_first_name,
        legal_last_name=legal_last_name,
        **kwargs,
    )
    db.add(resident)
    db.flush()
    return resident


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

    with session_scope(factory) as db:
        tenant = db.execute(
            select(Tenant).where(Tenant.facility_code == "demo-sandbox")
        ).scalar_one_or_none()
        if tenant is None:
            print(
                "ERROR: demo-sandbox tenant not found. Run "
                "`uv run python scripts/seed_sandbox.py` first.",
                file=sys.stderr,
            )
            return 1

        tid = tenant.id

        # ---------- Formulary ----------
        meds = {
            "lisinopril_20": _ensure_med(
                db,
                tenant_id=tid,
                name="Lisinopril",
                strength="20 mg",
                form="tablet",
            ),
            "metformin_500": _ensure_med(
                db,
                tenant_id=tid,
                name="Metformin",
                strength="500 mg",
                form="tablet",
            ),
            "atorvastatin_40": _ensure_med(
                db,
                tenant_id=tid,
                name="Atorvastatin",
                brand_name="Lipitor",
                strength="40 mg",
                form="tablet",
            ),
            "levothyroxine_75": _ensure_med(
                db,
                tenant_id=tid,
                name="Levothyroxine",
                strength="75 mcg",
                form="tablet",
            ),
            "acetaminophen_500": _ensure_med(
                db,
                tenant_id=tid,
                name="Acetaminophen",
                brand_name="Tylenol",
                strength="500 mg",
                form="tablet",
            ),
            "oxycodone_5": _ensure_med(
                db,
                tenant_id=tid,
                name="Oxycodone",
                strength="5 mg",
                form="tablet",
                schedule="II",
            ),
            "albuterol_inhaler": _ensure_med(
                db,
                tenant_id=tid,
                name="Albuterol",
                brand_name="ProAir HFA",
                strength="90 mcg/actuation",
                form="inhaler",
            ),
        }

        # ---------- Residents ----------
        residents = [
            _ensure_resident(
                db,
                tenant_id=tid,
                legal_first_name="Margaret",
                legal_last_name="Chen",
                preferred_name="Maggie",
                date_of_birth=dt.date(1942, 3, 14),
                gender="F",
                admission_date=dt.date.today() - dt.timedelta(days=420),
                room="201",
                bed="A",
                allergies_summary="Penicillin (rash)",
                code_status="dnr",
                fall_risk="moderate",
                dietary_restrictions="No added salt; thickened liquids",
                primary_physician_name="Dr. Aisha Patel",
                emergency_contact_name="Sarah Chen (daughter)",
                emergency_contact_relationship="Daughter",
                emergency_contact_phone="555-0142",
            ),
            _ensure_resident(
                db,
                tenant_id=tid,
                legal_first_name="Walter",
                legal_last_name="Brennan",
                preferred_name=None,
                date_of_birth=dt.date(1938, 11, 2),
                gender="M",
                admission_date=dt.date.today() - dt.timedelta(days=180),
                room="201",
                bed="B",
                allergies_summary="NKDA",
                code_status="full",
                fall_risk="high",
                dietary_restrictions="Diabetic; mechanical soft",
                primary_physician_name="Dr. Aisha Patel",
                emergency_contact_name="Tom Brennan (son)",
                emergency_contact_relationship="Son",
                emergency_contact_phone="555-0177",
                chart_note="Bed alarm in use. Wanderer — keep door alarm on at night.",
            ),
            _ensure_resident(
                db,
                tenant_id=tid,
                legal_first_name="Eleanor",
                legal_last_name="Whitfield",
                preferred_name="Ellie",
                date_of_birth=dt.date(1945, 7, 22),
                gender="F",
                admission_date=dt.date.today() - dt.timedelta(days=60),
                room="203",
                bed="A",
                allergies_summary="Sulfa drugs (anaphylaxis)",
                code_status="dnr_dni",
                fall_risk="low",
                dietary_restrictions="Vegetarian",
                primary_physician_name="Dr. Marcus Webb",
                emergency_contact_name="James Whitfield (husband)",
                emergency_contact_relationship="Spouse",
                emergency_contact_phone="555-0203",
            ),
        ]
        maggie, walter, ellie = residents

        # ---------- Sample orders ----------
        # Don't recreate orders if any exist for this resident.
        def _ensure_order(resident_id: int, **kwargs) -> None:
            exists = db.execute(
                select(MedicationOrder).where(
                    MedicationOrder.tenant_id == tid,
                    MedicationOrder.resident_id == resident_id,
                    MedicationOrder.medication_id == kwargs["medication_id"],
                    MedicationOrder.status.in_(("active", "pending", "held")),
                )
            ).scalar_one_or_none()
            if exists:
                return
            db.add(
                MedicationOrder(
                    tenant_id=tid,
                    resident_id=resident_id,
                    status="active",
                    **kwargs,
                )
            )

        _ensure_order(
            maggie.id,
            medication_id=meds["lisinopril_20"].id,
            dose="20 mg",
            route="oral",
            frequency="Daily",
            indication="Hypertension",
            prescriber_name="Dr. Aisha Patel",
            start_date=maggie.admission_date,
        )
        _ensure_order(
            maggie.id,
            medication_id=meds["levothyroxine_75"].id,
            dose="75 mcg",
            route="oral",
            frequency="Daily, before breakfast",
            indication="Hypothyroidism",
            prescriber_name="Dr. Aisha Patel",
            start_date=maggie.admission_date,
            instructions="Give 30 minutes before food",
        )
        _ensure_order(
            walter.id,
            medication_id=meds["metformin_500"].id,
            dose="500 mg",
            route="oral",
            frequency="BID with meals",
            indication="Type 2 diabetes",
            prescriber_name="Dr. Aisha Patel",
            start_date=walter.admission_date,
        )
        _ensure_order(
            walter.id,
            medication_id=meds["atorvastatin_40"].id,
            dose="40 mg",
            route="oral",
            frequency="Daily at bedtime",
            indication="Hyperlipidemia",
            prescriber_name="Dr. Aisha Patel",
            start_date=walter.admission_date,
        )
        _ensure_order(
            walter.id,
            medication_id=meds["oxycodone_5"].id,
            dose="5 mg",
            route="oral",
            frequency="Q6H PRN",
            is_prn=True,
            prn_indication="Severe pain (≥7/10)",
            prn_max_doses_per_24h=4,
            indication="Chronic back pain",
            prescriber_name="Dr. Aisha Patel",
            start_date=walter.admission_date,
            witness_required=True,
        )
        _ensure_order(
            ellie.id,
            medication_id=meds["albuterol_inhaler"].id,
            dose="2 puffs",
            route="inhaled",
            frequency="Q4H PRN",
            is_prn=True,
            prn_indication="Wheezing or shortness of breath",
            prn_max_doses_per_24h=6,
            indication="Asthma",
            prescriber_name="Dr. Marcus Webb",
            start_date=ellie.admission_date,
        )

        db.commit()
        print(f"✓ Seeded clinical demo into tenant id={tid} ({tenant.facility_code})")
        print(f"  - {len(meds)} medications in formulary")
        print(f"  - {len(residents)} residents (Maggie, Walter, Ellie)")
        print("  - 6 active medication orders across them")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
