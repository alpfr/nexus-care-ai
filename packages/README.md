# packages/

Internal Python packages shared by services. Each package is small, focused, and has no service-specific code.

Currently empty. Packages get added during the migration as cross-service code emerges. Likely entries:

- `tenancy/` — `current_tenant_id` context var, scoping helpers, tenant-state guards
- `auth/` — Argon2id PIN hashing, JWT issuer/verifier, `can()` permission helper
- `audit/` — append-only audit-log writer with PHI scrubber
- `llm/` — `LLMClient` interface + Gemini implementation + prompt loader
- `phi/` — PHI scrubbers, FHIR (de-)serialization helpers

## Pattern

Each package is its own uv workspace member with its own `pyproject.toml`:

```
packages/tenancy/
├── pyproject.toml
├── src/
│   └── nexus_care_tenancy/
│       ├── __init__.py
│       └── ...
└── tests/
```

Services depend on packages by adding them to their own `dependencies` list and resolving locally via `[tool.uv.sources]`.

## What does NOT belong here

- Service-specific business logic (lives in the service)
- Frontend code (lives in `apps/web`)
- Database models (live in `db/` — there is exactly one schema, shared)
