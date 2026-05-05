"""The Resident model — a person admitted to an LTC facility.

15 fields cover the realistic clinical chart minus the pieces that need
encryption-at-rest (SSN, full insurance numbers) which land in tranche 9.

Status lifecycle:
    admitted  ──► discharged
                  ──► deceased

Discharged and deceased are both terminal; the row is never deleted, just
marked. This matters for state surveys where a facility must be able to
produce a chart for a resident even years after discharge.

Soft-deletion is intentional and clinical: real-world residents come back
(re-admission), and even after they don't, the record is required for
audits, family inquiries, and statutory retention (typically 7-10 years).

Code status enumeration follows POLST/MOLST conventions:
    full          — full code (CPR, intubation, all interventions)
    dnr           — do not resuscitate
    dni           — do not intubate
    dnr_dni       — both
    comfort_only  — comfort care, no transfers, no escalation
    unknown       — not yet documented (force a clinical decision early)
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import (
    CheckConstraint,
    Date,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from nexus_care_db.base import TENANT_DATA_SCHEMA, Base, TimestampMixin


class Resident(Base, TimestampMixin):
    __tablename__ = "residents"
    __table_args__ = (
        # All clinical reads/writes are tenant-scoped. The composite index
        # accelerates the common "list active residents in this tenant" query.
        Index(
            "ix_residents_tenant_status",
            "tenant_id",
            "status",
        ),
        # Room/bed assignment must be unique within a tenant for active
        # residents — but we enforce that in application code, not the DB,
        # because:
        #   - bed numbers are nullable while a resident is in transit / pre-admit
        #   - "active" is a status, and a partial unique index gets unwieldy
        # The application layer checks before assigning.
        CheckConstraint(
            "status IN ('admitted', 'discharged', 'deceased')",
            name="resident_status_valid",
        ),
        CheckConstraint(
            "code_status IN ('full', 'dnr', 'dni', 'dnr_dni', 'comfort_only', 'unknown')",
            name="resident_code_status_valid",
        ),
        CheckConstraint(
            "fall_risk IN ('low', 'moderate', 'high', 'unassessed')",
            name="resident_fall_risk_valid",
        ),
        {"schema": TENANT_DATA_SCHEMA},
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    # The tenant gate. Non-null, indexed. Every resident row is owned by
    # exactly one facility. Cross-tenant reads/writes are blocked at the
    # application layer; this column is the truth.
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    # ---- Identity ----
    legal_first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    legal_last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    preferred_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    date_of_birth: Mapped[dt.date] = mapped_column(Date, nullable=False)

    # Free-text — we store self-identified gender rather than enforce an
    # enumeration. Some facilities want "M/F" only; some want fuller options.
    # Validation lives in the application layer where it can be configured.
    gender: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # ---- Admission ----
    admission_date: Mapped[dt.date] = mapped_column(Date, nullable=False)
    discharge_date: Mapped[dt.date | None] = mapped_column(Date, nullable=True)

    # status drives the gated state machine in routes/clinical/residents.py
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        server_default=text("'admitted'"),
    )

    # ---- Location ----
    # Room + bed. Nullable for residents in transit. Application layer
    # enforces uniqueness of (room, bed) among active residents in a tenant.
    room: Mapped[str | None] = mapped_column(String(16), nullable=True)
    bed: Mapped[str | None] = mapped_column(String(16), nullable=True)

    # ---- Clinical critical info ----
    # Short text — known allergies, free-form. A structured `Allergy` table
    # lands later when we wire allergy-checking into the eMAR.
    allergies_summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    # POLST/MOLST code status. Defaults to 'unknown' to force a clinical
    # decision before any orders are placed. UI surfaces this prominently
    # and blocks PRN-pain orders if 'unknown'.
    code_status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        server_default=text("'unknown'"),
    )

    # Fall risk — 'low' | 'moderate' | 'high' | 'unassessed'. Drives bed-alarm
    # display and care-plan auto-population in later tranches.
    fall_risk: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        server_default=text("'unassessed'"),
    )

    # Free-text dietary restrictions. A structured Diet model lands when
    # we port the meal-tray system. For now this is a sufficient summary.
    dietary_restrictions: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ---- Care team ----
    # Just text for now — we'll relate to a Provider table when we model
    # those (requires NPI, DEA, etc.). Storing the name unblocks display.
    primary_physician_name: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # ---- Emergency contact ----
    emergency_contact_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    emergency_contact_relationship: Mapped[str | None] = mapped_column(String(64), nullable=True)
    emergency_contact_phone: Mapped[str | None] = mapped_column(String(32), nullable=True)

    # ---- Notes ----
    # Free-text caveat field for things that don't fit elsewhere. NOT a
    # clinical-notes log (that's a separate table later). For brief flags
    # like "always wears red socks; says it brings luck — please respect".
    chart_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Convenience computed property — not a column. Useful in APIs and UI.
    @property
    def display_name(self) -> str:
        """Return the preferred name if set, else legal first name + last initial."""
        if self.preferred_name:
            return f"{self.preferred_name} {self.legal_last_name}"
        return f"{self.legal_first_name} {self.legal_last_name}"

    @property
    def is_active(self) -> bool:
        return self.status == "admitted"
