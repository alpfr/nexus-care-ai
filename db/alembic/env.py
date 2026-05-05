"""Alembic migration environment for Nexus Care AI.

This file:
  1. Loads the DATABASE_URL from the environment.
  2. Imports every model so Alembic can discover the metadata.
  3. Configures Alembic to manage BOTH the `platform` and `tenant_data`
     Postgres schemas (creating them if needed at the start of the very
     first migration).
"""

from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context

# Import the Base + all models so metadata is populated for autogenerate.
from nexus_care_db import Base
from nexus_care_db.base import PLATFORM_SCHEMA, TENANT_DATA_SCHEMA
from sqlalchemy import engine_from_config, pool

config = context.config

# Pull the database URL from the environment. Never hardcode.
database_url = os.environ.get("DATABASE_URL")
if not database_url:
    raise RuntimeError(
        "DATABASE_URL is not set. Export it before running alembic.\n"
        "Local dev example:\n"
        "  export DATABASE_URL='postgresql+psycopg://nexus:nexus@localhost:5433/nexus_care'"
    )
config.set_main_option("sqlalchemy.url", database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# Schemas Alembic should consider when comparing schema state.
# include_schemas=True tells autogenerate to look at *all* schemas the
# connection user can see; we filter to only ours via include_object below.
TRACKED_SCHEMAS = {PLATFORM_SCHEMA, TENANT_DATA_SCHEMA}


def include_object(obj, name, type_, reflected, compare_to):
    """Skip objects that aren't in the schemas we manage."""
    return not (type_ == "table" and obj.schema not in TRACKED_SCHEMAS)


def run_migrations_offline() -> None:
    context.configure(
        url=database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_schemas=True,
        include_object=include_object,
        version_table_schema=PLATFORM_SCHEMA,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        # Make sure both schemas exist before Alembic tries to put the
        # alembic_version table in `platform`. CREATE SCHEMA IF NOT EXISTS
        # is idempotent and safe to run on every migrate.
        connection.exec_driver_sql(f'CREATE SCHEMA IF NOT EXISTS "{PLATFORM_SCHEMA}"')
        connection.exec_driver_sql(f'CREATE SCHEMA IF NOT EXISTS "{TENANT_DATA_SCHEMA}"')
        connection.commit()

        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_schemas=True,
            include_object=include_object,
            version_table_schema=PLATFORM_SCHEMA,
            compare_type=True,
            compare_server_default=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
