"""The Medication model — a drug in the facility's formulary.

This is the catalog: "Lisinopril 20mg tablet" lives here once, and many
MedicationOrders point to it. Different facilities curate different
formularies, so this is tenant-scoped (some chains share a corporate
formulary; we model that with feature flags later).

Schedule (DEA controlled-substance schedule) drives med-pass UI:
  - Schedules II-V require witness counts and special handling
  - 'none' is uncontrolled / OTC

Form is the dosage form: tablet, capsule, liquid, patch, injection, etc.
We use a string with a check constraint rather than a Postgres enum so
new forms can be added without migrations.

The dose, route, and frequency live on MedicationOrder, NOT here. The
catalog stores "what this drug is" — orders express "how this drug is
prescribed for this resident." Same drug, multiple dose strengths in
the catalog, multiple orders per strength. Realistic.
"""

from __future__ import annotations

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from nexus_care_db.base import TENANT_DATA_SCHEMA, Base, TimestampMixin


class Medication(Base, TimestampMixin):
    __tablename__ = "medications"
    __table_args__ = (
        # Same drug at the same strength can appear once per tenant.
        UniqueConstraint(
            "tenant_id", "name", "strength", name="uq_medications_tenant_name_strength"
        ),
        Index("ix_medications_tenant_name", "tenant_id", "name"),
        CheckConstraint(
            "schedule IN ('none', 'II', 'III', 'IV', 'V')",
            name="medication_schedule_valid",
        ),
        CheckConstraint(
            "form IN ('tablet', 'capsule', 'liquid', 'oral_solution', 'suspension', "
            "'patch', 'cream', 'ointment', 'inhaler', 'nebulizer_solution', "
            "'injection', 'suppository', 'eye_drop', 'ear_drop', 'other')",
            name="medication_form_valid",
        ),
        {"schema": TENANT_DATA_SCHEMA},
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    # Generic name preferred ("Lisinopril"). Brand name optional and shown
    # parenthetically in the UI when set. Pharmacists prefer generics; some
    # nurses recognize brands; we surface both when available.
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    brand_name: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # Strength as a string because dose forms vary wildly: "20 mg", "5 mg/mL",
    # "50,000 IU", "0.025 mg/24hr". Parsing is intentionally not done here.
    strength: Mapped[str] = mapped_column(String(64), nullable=False)

    form: Mapped[str] = mapped_column(String(32), nullable=False)

    # DEA schedule. 'none' for uncontrolled drugs (most of the formulary).
    # Drives witness-required flow + count tracking in tranche 6c.
    schedule: Mapped[str] = mapped_column(
        String(8),
        nullable=False,
        server_default=text("'none'"),
    )

    # Active = currently dispensable. When a drug is removed from the
    # formulary, we set is_active=false rather than deleting (existing
    # orders may still reference it for historical accuracy).
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("true"),
    )

    # Optional notes for nurses / pharmacy. Things like
    # "must be administered with food" or "store refrigerated".
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    @property
    def display_name(self) -> str:
        """Drug name + strength + form for UI lists, e.g.,
        'Lisinopril 20 mg tablet'."""
        return f"{self.name} {self.strength} {self.form}"

    @property
    def is_controlled(self) -> bool:
        return self.schedule != "none"
