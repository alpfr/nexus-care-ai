# db/

Database schema, migrations, and seed data. **Single source of truth** for what the database looks like.

```
db/
├── pyproject.toml         uv workspace member
├── src/nexus_care_db/     SQLAlchemy models (typed Mapped style)
│   ├── platform/          platform schema models (tenants, billing, ...)
│   └── tenant_data/       tenant_data schema models (residents, meds, ...)
├── alembic/               migrations
│   ├── env.py
│   └── versions/          numbered migration scripts
├── alembic.ini            alembic config (lands in tranche 2)
└── seed/                  seed data for local dev + tests
```

## Why a single shared package

Both `services/api` and `services/platform` depend on the same database, in different schemas. If each service had its own model definitions we'd inevitably drift — a column added in one wouldn't exist in the other's view of the world. Centralizing models in this package makes drift impossible.

## Schema separation in one database

We use Postgres schemas (namespaces inside one database) rather than separate databases:

- `platform` schema: tenants, subscriptions, feature_flags, baa_artifacts, identity_verifications, platform_admins.
- `tenant_data` schema: residents, medications, clinical_notes, audit_log, and everything else with a `tenant_id` column.

`services/platform` is granted access to `platform.*` only. `services/api` is granted access to both — read-only on `platform` (for the per-request tenant lookup) and full on `tenant_data`.

## Migration workflow

Once Alembic lands in tranche 2:

```bash
# Create a new migration
uv run alembic -c db/alembic.ini revision --autogenerate -m "add_resident_status"

# Run pending migrations
uv run alembic -c db/alembic.ini upgrade head

# Roll back one step
uv run alembic -c db/alembic.ini downgrade -1
```

**Never** edit a migration that's already been applied to staging or production. Always write a forward-only migration to fix it.
