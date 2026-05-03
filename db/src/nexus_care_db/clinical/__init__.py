"""Clinical models — PHI-bearing tables.

These tables hold protected health information. Every row carries a non-null
`tenant_id` and every PHI write goes through the gated state machine in
nexus_care_tenancy (sandbox tenants cannot write here).

Lives in the `tenant_data` Postgres schema (set by Base.metadata) alongside
the audit_log. The platform schema is reserved for SaaS plumbing and does
not contain PHI.
"""
