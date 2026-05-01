"""Models in the `platform` Postgres schema.

These tables hold tenant lifecycle, billing, feature flags, BAA artifacts,
identity verifications, and platform-admin users. They do NOT hold PHI.

The `services/platform` service has full access. The `services/api` service
has read-only access for the per-request tenant lookup.
"""
