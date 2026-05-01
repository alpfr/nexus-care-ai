# services/

Backend services. Each service is its own deployable, with its own API surface, its own Dockerfile, and its own auth model.

- [`api/`](api/) — clinical + AI service. Tenant-scoped. PIN+JWT auth. Serves `/api/*`.
- [`platform/`](platform/) — SaaS platform admin service. Manages tenant lifecycle, billing, feature flags, BAA artifacts. Platform-admin auth (separate from clinician auth). Serves `/api/platform/*`.

Both services share the database schema package (`db/`) and validation/utility packages (`packages/*`). They do **not** import from each other directly — cross-service contracts go through HTTP.

## Why two services instead of one

Three reasons:

1. **Blast radius.** A bug in the platform service should not be able to read clinical data. Separate services + separate auth = a bright line.
2. **Different deploy cadences.** Platform changes (billing, tenant lifecycle) ship without disturbing clinical workflows.
3. **Different scaling profiles.** Platform traffic is low-volume admin. Clinical traffic is high-volume bedside. Different replica counts, different SLAs.

In Phase 1 both services live in the same Postgres database (in different schemas). Splitting databases later is straightforward if scale demands it.
