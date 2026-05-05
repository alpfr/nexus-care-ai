"""The MedicationOrder model — a specific prescription for a specific resident.

A MedicationOrder ties a Resident to a Medication and adds the prescribing
context: dose, route, frequency, indication, prescriber. Each order is the
authoritative answer to "what is this resident supposed to be receiving?"

The eMAR (lands in 6b) joins active MedicationOrders to actual administration
events. An order without administrations is just a plan; an administration
without an order is a documentation error.

State machine:
    pending  ──► active  ──► discontinued
                 ──► held       (temporarily paused, e.g., NPO before surgery)
                          ──► active     (resumed)
                          ──► discontinued

Pending = entered but not yet activated (waiting for pharmacy review,
prescriber signature). Most orders go pending → active immediately in the
UI; the state exists for facilities that have a pharmacist-review workflow.

Held = temporarily paused. A held order does not appear on the eMAR for
administration but the order itself is preserved. Common reasons:
"NPO before surgery," "elevated INR — hold warfarin x 1 dose."

Discontinued is terminal (no transitions out). Re-prescribing creates a
new order, which is correct: a new clinical decision deserves a new audit
trail.

Frequency is intentionally a free-text-ish string in 6a ("BID", "Q8H",
"with breakfast"). A structured Schedule lands in 6b alongside eMAR — the
schedule IS the eMAR's primary lookup.
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from nexus_care_db.base import TENANT_DATA_SCHEMA, Base, TimestampMixin


class MedicationOrder(Base, TimestampMixin):
    __tablename__ = "medication_orders"
    __table_args__ = (
        # Common queries:
        #   "show all active orders for a resident" → tenant + resident + status
        #   "show all orders by drug across residents" (pharmacy review) → tenant + medication
        Index(
            "ix_medication_orders_tenant_resident_status",
            "tenant_id",
            "resident_id",
            "status",
        ),
        Index(
            "ix_medication_orders_tenant_medication",
            "tenant_id",
            "medication_id",
        ),
        CheckConstraint(
            "status IN ('pending', 'active', 'held', 'discontinued')",
            name="medication_order_status_valid",
        ),
        CheckConstraint(
            "route IN ('oral', 'sublingual', 'topical', 'transdermal', 'inhaled', "
            "'nebulized', 'subcutaneous', 'intramuscular', 'intravenous', "
            "'rectal', 'ophthalmic', 'otic', 'nasal', 'other')",
            name="medication_order_route_valid",
        ),
        CheckConstraint(
            "is_prn IN (true, false)",
            name="medication_order_is_prn_valid",
        ),
        {"schema": TENANT_DATA_SCHEMA},
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    # ---- The two parties ----
    resident_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey(f"{TENANT_DATA_SCHEMA}.residents.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    medication_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey(f"{TENANT_DATA_SCHEMA}.medications.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    # ---- The prescription ----
    # Dose as a string for the same reason Medication.strength is — units
    # vary too widely. UI surfaces this as-typed.
    dose: Mapped[str] = mapped_column(String(64), nullable=False)

    route: Mapped[str] = mapped_column(String(32), nullable=False)

    # Frequency as free-text in 6a; structured Schedule lands in 6b.
    # Examples we expect: "BID", "Q8H", "Daily at bedtime", "Every Mon/Wed/Fri".
    frequency: Mapped[str] = mapped_column(String(128), nullable=False)

    # PRN = "as needed". Not part of 6b's first eMAR build; a column here so
    # the data model is right from the start. is_prn=True orders need a
    # `prn_indication` to be useful to the administering nurse.
    is_prn: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("false"),
    )
    prn_indication: Mapped[str | None] = mapped_column(String(255), nullable=True)
    prn_max_doses_per_24h: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Why is the resident getting this drug? Required clinically. Examples:
    # "hypertension", "post-op pain", "atrial fibrillation rate control".
    indication: Mapped[str] = mapped_column(String(255), nullable=False)

    # Free-text instructions to the administering nurse. Things like
    # "give 30 min before breakfast" or "crush and mix with applesauce".
    instructions: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ---- Prescriber ----
    # Just a name string for now (same reasoning as Resident.primary_physician_name).
    # When we model Provider, we'll add a nullable provider_id column and
    # backfill.
    prescriber_name: Mapped[str] = mapped_column(String(200), nullable=False)

    # ---- Timing ----
    start_date: Mapped[dt.date] = mapped_column(Date, nullable=False)
    end_date: Mapped[dt.date | None] = mapped_column(Date, nullable=True)

    # ---- State ----
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        server_default=text("'pending'"),
        index=True,
    )

    # When status changes to 'discontinued', record why. Required by audit.
    # Same with 'held' (e.g., "NPO for procedure 5/8").
    status_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ---- Witness flag ----
    # Set true automatically for Schedule II-V meds when the order is created.
    # The actual witness-signing flow lands in 6c; for now this is a hint
    # to the UI to display a "Witness required" badge.
    witness_required: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("false"),
    )

    discontinued_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
