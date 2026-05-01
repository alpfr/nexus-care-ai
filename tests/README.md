# tests/

Cross-service integration and end-to-end tests. **Service-internal unit tests live next to the code they test** (e.g., `services/api/tests/`); this folder is for tests that exercise multiple services together.

Current planned contents:

- `integration/` — full-stack integration tests (API + platform + DB)
- `e2e/` — Playwright tests that drive the browser against the running stack
- `tenant_isolation/` — dedicated cross-tenant isolation tests, run on every PR

Empty in tranche 1; populated as the system grows.

## Tenant-isolation tests are non-negotiable

Every PHI-bearing model gets a corresponding isolation test that:

1. Creates two tenants and seeds them with similar data.
2. Logs in as a user from tenant A.
3. Attempts to read or write tenant B's data.
4. Asserts the attempt fails (404, not 403 — we don't reveal that the resource exists).

If a port adds a model and skips this test, CI must reject it. We'll wire that into the CI workflow in tranche 5.
