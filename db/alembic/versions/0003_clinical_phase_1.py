"""clinical phase 1: residents, medications, medication_orders

Revision ID: 0003_clinical_phase_1
Revises: 0002_platform_admins
Create Date: 2026-05-03

Adds:
  - tenant_data.residents
  - tenant_data.medications
  - tenant_data.medication_orders

These are the core PHI-bearing tables for tranche 6a. eMAR / vitals / ADL
land in 6b on top of these.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_clinical_phase_1"
down_revision: str | None = "0002_platform_admins"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ---------- tenant_data.residents ----------
    op.create_table(
        "residents",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("legal_first_name", sa.String(length=100), nullable=False),
        sa.Column("legal_last_name", sa.String(length=100), nullable=False),
        sa.Column("preferred_name", sa.String(length=100), nullable=True),
        sa.Column("date_of_birth", sa.Date(), nullable=False),
        sa.Column("gender", sa.String(length=50), nullable=True),
        sa.Column("admission_date", sa.Date(), nullable=False),
        sa.Column("discharge_date", sa.Date(), nullable=True),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            server_default=sa.text("'admitted'"),
        ),
        sa.Column("room", sa.String(length=16), nullable=True),
        sa.Column("bed", sa.String(length=16), nullable=True),
        sa.Column("allergies_summary", sa.Text(), nullable=True),
        sa.Column(
            "code_status",
            sa.String(length=32),
            nullable=False,
            server_default=sa.text("'unknown'"),
        ),
        sa.Column(
            "fall_risk",
            sa.String(length=32),
            nullable=False,
            server_default=sa.text("'unassessed'"),
        ),
        sa.Column("dietary_restrictions", sa.Text(), nullable=True),
        sa.Column("primary_physician_name", sa.String(length=200), nullable=True),
        sa.Column("emergency_contact_name", sa.String(length=200), nullable=True),
        sa.Column(
            "emergency_contact_relationship", sa.String(length=64), nullable=True
        ),
        sa.Column("emergency_contact_phone", sa.String(length=32), nullable=True),
        sa.Column("chart_note", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "status IN ('admitted', 'discharged', 'deceased')",
            name="ck_residents_resident_status_valid",
        ),
        sa.CheckConstraint(
            "code_status IN ('full', 'dnr', 'dni', 'dnr_dni', 'comfort_only', 'unknown')",
            name="ck_residents_resident_code_status_valid",
        ),
        sa.CheckConstraint(
            "fall_risk IN ('low', 'moderate', 'high', 'unassessed')",
            name="ck_residents_resident_fall_risk_valid",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_residents"),
        schema="tenant_data",
    )
    op.create_index(
        "ix_tenant_data_residents_tenant_id",
        "residents",
        ["tenant_id"],
        schema="tenant_data",
    )
    op.create_index(
        "ix_residents_tenant_status",
        "residents",
        ["tenant_id", "status"],
        schema="tenant_data",
    )

    # ---------- tenant_data.medications ----------
    op.create_table(
        "medications",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("brand_name", sa.String(length=200), nullable=True),
        sa.Column("strength", sa.String(length=64), nullable=False),
        sa.Column("form", sa.String(length=32), nullable=False),
        sa.Column(
            "schedule",
            sa.String(length=8),
            nullable=False,
            server_default=sa.text("'none'"),
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "schedule IN ('none', 'II', 'III', 'IV', 'V')",
            name="ck_medications_medication_schedule_valid",
        ),
        sa.CheckConstraint(
            "form IN ('tablet', 'capsule', 'liquid', 'oral_solution', 'suspension', "
            "'patch', 'cream', 'ointment', 'inhaler', 'nebulizer_solution', "
            "'injection', 'suppository', 'eye_drop', 'ear_drop', 'other')",
            name="ck_medications_medication_form_valid",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_medications"),
        sa.UniqueConstraint(
            "tenant_id", "name", "strength", name="uq_medications_tenant_name_strength"
        ),
        schema="tenant_data",
    )
    op.create_index(
        "ix_tenant_data_medications_tenant_id",
        "medications",
        ["tenant_id"],
        schema="tenant_data",
    )
    op.create_index(
        "ix_medications_tenant_name",
        "medications",
        ["tenant_id", "name"],
        schema="tenant_data",
    )

    # ---------- tenant_data.medication_orders ----------
    op.create_table(
        "medication_orders",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("resident_id", sa.Integer(), nullable=False),
        sa.Column("medication_id", sa.Integer(), nullable=False),
        sa.Column("dose", sa.String(length=64), nullable=False),
        sa.Column("route", sa.String(length=32), nullable=False),
        sa.Column("frequency", sa.String(length=128), nullable=False),
        sa.Column(
            "is_prn",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("prn_indication", sa.String(length=255), nullable=True),
        sa.Column("prn_max_doses_per_24h", sa.Integer(), nullable=True),
        sa.Column("indication", sa.String(length=255), nullable=False),
        sa.Column("instructions", sa.Text(), nullable=True),
        sa.Column("prescriber_name", sa.String(length=200), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column("status_reason", sa.Text(), nullable=True),
        sa.Column(
            "witness_required",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("discontinued_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'active', 'held', 'discontinued')",
            name="ck_medication_orders_medication_order_status_valid",
        ),
        sa.CheckConstraint(
            "route IN ('oral', 'sublingual', 'topical', 'transdermal', 'inhaled', "
            "'nebulized', 'subcutaneous', 'intramuscular', 'intravenous', "
            "'rectal', 'ophthalmic', 'otic', 'nasal', 'other')",
            name="ck_medication_orders_medication_order_route_valid",
        ),
        sa.CheckConstraint(
            "is_prn IN (true, false)",
            name="ck_medication_orders_medication_order_is_prn_valid",
        ),
        sa.ForeignKeyConstraint(
            ["resident_id"],
            ["tenant_data.residents.id"],
            name="fk_medication_orders_resident_id_residents",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["medication_id"],
            ["tenant_data.medications.id"],
            name="fk_medication_orders_medication_id_medications",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_medication_orders"),
        schema="tenant_data",
    )
    op.create_index(
        "ix_tenant_data_medication_orders_tenant_id",
        "medication_orders",
        ["tenant_id"],
        schema="tenant_data",
    )
    op.create_index(
        "ix_tenant_data_medication_orders_resident_id",
        "medication_orders",
        ["resident_id"],
        schema="tenant_data",
    )
    op.create_index(
        "ix_tenant_data_medication_orders_medication_id",
        "medication_orders",
        ["medication_id"],
        schema="tenant_data",
    )
    op.create_index(
        "ix_tenant_data_medication_orders_status",
        "medication_orders",
        ["status"],
        schema="tenant_data",
    )
    op.create_index(
        "ix_medication_orders_tenant_resident_status",
        "medication_orders",
        ["tenant_id", "resident_id", "status"],
        schema="tenant_data",
    )
    op.create_index(
        "ix_medication_orders_tenant_medication",
        "medication_orders",
        ["tenant_id", "medication_id"],
        schema="tenant_data",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_medication_orders_tenant_medication",
        table_name="medication_orders",
        schema="tenant_data",
    )
    op.drop_index(
        "ix_medication_orders_tenant_resident_status",
        table_name="medication_orders",
        schema="tenant_data",
    )
    op.drop_index(
        "ix_tenant_data_medication_orders_status",
        table_name="medication_orders",
        schema="tenant_data",
    )
    op.drop_index(
        "ix_tenant_data_medication_orders_medication_id",
        table_name="medication_orders",
        schema="tenant_data",
    )
    op.drop_index(
        "ix_tenant_data_medication_orders_resident_id",
        table_name="medication_orders",
        schema="tenant_data",
    )
    op.drop_index(
        "ix_tenant_data_medication_orders_tenant_id",
        table_name="medication_orders",
        schema="tenant_data",
    )
    op.drop_table("medication_orders", schema="tenant_data")

    op.drop_index(
        "ix_medications_tenant_name", table_name="medications", schema="tenant_data"
    )
    op.drop_index(
        "ix_tenant_data_medications_tenant_id",
        table_name="medications",
        schema="tenant_data",
    )
    op.drop_table("medications", schema="tenant_data")

    op.drop_index(
        "ix_residents_tenant_status", table_name="residents", schema="tenant_data"
    )
    op.drop_index(
        "ix_tenant_data_residents_tenant_id",
        table_name="residents",
        schema="tenant_data",
    )
    op.drop_table("residents", schema="tenant_data")
