"""initial schema: tenants, users, audit_log

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-05-01

Creates the foundation: the platform schema (tenants + users) and the
tenant_data schema (audit_log). All clinical models land in later
migrations.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001_initial_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ---------- platform.tenants ----------
    op.create_table(
        "tenants",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("facility_code", sa.String(length=32), nullable=False),
        sa.Column(
            "state",
            sa.String(length=32),
            nullable=False,
            server_default=sa.text("'sandbox'"),
        ),
        sa.Column(
            "region_code",
            sa.String(length=32),
            nullable=False,
            server_default=sa.text("'us-central'"),
        ),
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
            "state IN ('sandbox', 'pending_activation', 'active', 'suspended', 'terminated')",
            name="ck_tenants_tenant_state_valid",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_tenants"),
        sa.UniqueConstraint("facility_code", name="uq_tenants_facility_code"),
        schema="platform",
    )
    op.create_index(
        "ix_platform_tenants_facility_code",
        "tenants",
        ["facility_code"],
        unique=True,
        schema="platform",
    )
    op.create_index(
        "ix_platform_tenants_state",
        "tenants",
        ["state"],
        unique=False,
        schema="platform",
    )

    # ---------- platform.users ----------
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("full_name", sa.String(length=200), nullable=False),
        sa.Column("pin_hash", sa.String(length=255), nullable=False),
        sa.Column("pin_hash_lookup", sa.String(length=64), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "failed_login_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "tokens_invalid_after",
            sa.BigInteger(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
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
            "role IN ('nurse', 'med_tech', 'caregiver', 'supervisor', "
            "'tenant_admin', 'platform_admin')",
            name="ck_users_user_role_valid",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["platform.tenants.id"],
            name="fk_users_tenant_id_tenants",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
        sa.UniqueConstraint(
            "tenant_id", "pin_hash_lookup", name="user_unique_pin_per_tenant"
        ),
        schema="platform",
    )
    op.create_index(
        "ix_platform_users_tenant_id", "users", ["tenant_id"], schema="platform"
    )
    op.create_index(
        "ix_platform_users_pin_hash_lookup",
        "users",
        ["pin_hash_lookup"],
        schema="platform",
    )

    # ---------- tenant_data.audit_log ----------
    op.create_table(
        "audit_log",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("tenant_state", sa.String(length=32), nullable=False),
        sa.Column("action", sa.String(length=32), nullable=False),
        sa.Column("entity_type", sa.String(length=64), nullable=False),
        sa.Column("entity_id", sa.String(length=64), nullable=True),
        sa.Column("outcome", sa.String(length=16), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("provenance_data", sa.JSON(), nullable=True),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id", name="pk_audit_log"),
        schema="tenant_data",
    )
    op.create_index(
        "ix_tenant_data_audit_log_tenant_id",
        "audit_log",
        ["tenant_id"],
        schema="tenant_data",
    )
    op.create_index(
        "ix_audit_log_tenant_entity",
        "audit_log",
        ["tenant_id", "entity_type", "entity_id", "occurred_at"],
        schema="tenant_data",
    )
    op.create_index(
        "ix_audit_log_tenant_actor",
        "audit_log",
        ["tenant_id", "actor_user_id", "occurred_at"],
        schema="tenant_data",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_audit_log_tenant_actor", table_name="audit_log", schema="tenant_data"
    )
    op.drop_index(
        "ix_audit_log_tenant_entity", table_name="audit_log", schema="tenant_data"
    )
    op.drop_index(
        "ix_tenant_data_audit_log_tenant_id",
        table_name="audit_log",
        schema="tenant_data",
    )
    op.drop_table("audit_log", schema="tenant_data")

    op.drop_index(
        "ix_platform_users_pin_hash_lookup", table_name="users", schema="platform"
    )
    op.drop_index("ix_platform_users_tenant_id", table_name="users", schema="platform")
    op.drop_table("users", schema="platform")

    op.drop_index(
        "ix_platform_tenants_state", table_name="tenants", schema="platform"
    )
    op.drop_index(
        "ix_platform_tenants_facility_code", table_name="tenants", schema="platform"
    )
    op.drop_table("tenants", schema="platform")
