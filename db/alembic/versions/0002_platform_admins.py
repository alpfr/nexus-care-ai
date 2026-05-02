"""platform admins, feature flags, tenant activation pipeline

Revision ID: 0002_platform_admins
Revises: 0001_initial_schema
Create Date: 2026-05-02

Adds:
  - platform.platform_admins  (Nexus Care AI staff who manage tenants)
  - platform.feature_flags    (per-tenant feature toggles)
  - extra columns on platform.tenants for the activation pipeline
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_platform_admins"
down_revision: str | None = "0001_initial_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ---------- platform.platform_admins ----------
    op.create_table(
        "platform_admins",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("full_name", sa.String(length=200), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
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
        sa.PrimaryKeyConstraint("id", name="pk_platform_admins"),
        sa.UniqueConstraint("email", name="uq_platform_admins_email"),
        schema="platform",
    )
    op.create_index(
        "ix_platform_platform_admins_email",
        "platform_admins",
        ["email"],
        unique=True,
        schema="platform",
    )

    # ---------- platform.feature_flags ----------
    op.create_table(
        "feature_flags",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("flag_key", sa.String(length=64), nullable=False),
        sa.Column(
            "enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.Column("config", sa.JSON(), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["platform.tenants.id"],
            name="fk_feature_flags_tenant_id_tenants",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_feature_flags"),
        sa.UniqueConstraint(
            "tenant_id", "flag_key", name="uq_feature_flags_tenant_id_flag_key"
        ),
        schema="platform",
    )
    op.create_index(
        "ix_platform_feature_flags_tenant_id",
        "feature_flags",
        ["tenant_id"],
        schema="platform",
    )

    # ---------- platform.tenants : add activation columns ----------
    op.add_column(
        "tenants",
        sa.Column(
            "activation_requested_by_user_id", sa.Integer(), nullable=True
        ),
        schema="platform",
    )
    op.add_column(
        "tenants",
        sa.Column(
            "activation_requested_at", sa.DateTime(timezone=True), nullable=True
        ),
        schema="platform",
    )
    op.add_column(
        "tenants",
        sa.Column("activated_by_admin_id", sa.Integer(), nullable=True),
        schema="platform",
    )
    op.add_column(
        "tenants",
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        schema="platform",
    )
    op.add_column(
        "tenants",
        sa.Column("baa_artifact_ref", sa.String(length=255), nullable=True),
        schema="platform",
    )
    op.add_column(
        "tenants",
        sa.Column(
            "identity_verification_ref", sa.String(length=255), nullable=True
        ),
        schema="platform",
    )
    op.add_column(
        "tenants",
        sa.Column("state_reason", sa.Text(), nullable=True),
        schema="platform",
    )

    op.create_foreign_key(
        "fk_tenants_activation_requested_by_user_id_users",
        "tenants",
        "users",
        ["activation_requested_by_user_id"],
        ["id"],
        source_schema="platform",
        referent_schema="platform",
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_tenants_activated_by_admin_id_platform_admins",
        "tenants",
        "platform_admins",
        ["activated_by_admin_id"],
        ["id"],
        source_schema="platform",
        referent_schema="platform",
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_tenants_activated_by_admin_id_platform_admins",
        "tenants",
        type_="foreignkey",
        schema="platform",
    )
    op.drop_constraint(
        "fk_tenants_activation_requested_by_user_id_users",
        "tenants",
        type_="foreignkey",
        schema="platform",
    )
    op.drop_column("tenants", "state_reason", schema="platform")
    op.drop_column("tenants", "identity_verification_ref", schema="platform")
    op.drop_column("tenants", "baa_artifact_ref", schema="platform")
    op.drop_column("tenants", "activated_at", schema="platform")
    op.drop_column("tenants", "activated_by_admin_id", schema="platform")
    op.drop_column("tenants", "activation_requested_at", schema="platform")
    op.drop_column(
        "tenants", "activation_requested_by_user_id", schema="platform"
    )

    op.drop_index(
        "ix_platform_feature_flags_tenant_id",
        table_name="feature_flags",
        schema="platform",
    )
    op.drop_table("feature_flags", schema="platform")

    op.drop_index(
        "ix_platform_platform_admins_email",
        table_name="platform_admins",
        schema="platform",
    )
    op.drop_table("platform_admins", schema="platform")
