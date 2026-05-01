"""Models in the `tenant_data` Postgres schema.

These tables hold all clinical PHI plus the audit log. Every row carries a
non-null `tenant_id` for cross-tenant isolation.

Only the `services/api` service writes to these tables. Platform service
has no access.
"""
