# ADR-0001: Initial stack and architecture for Nexus Care AI

- **Status:** accepted
- **Date:** 2026-05-01
- **Deciders:** alpfr, with architectural review

## Context

Nexus Care AI consolidates two predecessor codebases:

- **`smart-care-ai`** — Python/FastAPI + Next.js 16 + Gemini AI, with a working multi-tenant SaaS pattern, production-grade auth (PIN + Argon2id-shaped + JWT + lockout), tested cross-tenant isolation, and FHIR R4 export. Weaknesses: flat data model, SQLite-only inline migration code, missing several LTC compliance modules.
- **`NexusLTC`** — Node/Express + Vite/React + Postgres, with a richly normalized PALTC/FHIR-aligned schema and the LTC-compliance-critical modules (MDS 3.0, ADL, care plans with goals/interventions, physician orders, vital signs, consent + rights acknowledgment, retention policies, document sharing, medical team contacts). Critical weakness: auth accepts any 4+ char PIN with unsigned base64 "tokens" — not safe to ship.

The product target is a multi-tenant SaaS LTC EHR with an AI-native documentation assistant and bedside-mobile UX, launching publicly as a sandbox in June 2026 with one design-partner customer on real PHI by Q3 2026, and reaching general availability with SOC 2 Type II in Q1 2027.

## Decision

We are scaffolding a new repository (`nexus-care-ai`) and porting features from both predecessors into it incrementally rather than merging either repository wholesale. The stack and architectural patterns are:

**Backend:** Python 3.13, FastAPI 0.136, SQLAlchemy 2.0 (typed mapped style), Alembic for migrations, Pydantic 2.13, argon2-cffi (Argon2id), PyJWT, structlog, Ruff, pytest, uv as the package and Python-version manager.

**Frontend:** Next.js 16.2 (App Router, Turbopack, React Compiler), React 19.2, TypeScript strict, Tailwind v4, shadcn/ui (copy-in components), TanStack Query for server-state cache, react-hook-form + Zod for forms, Zustand for cross-page UI state, Vitest + Testing Library + Playwright for tests, bun as the package manager and runtime.

**Database:** PostgreSQL 18.3 with `uuidv7()` primary keys for high-volume audit/administration tables, two schemas in one database (`platform` for tenant lifecycle and `tenant_data` for clinical data), SCRAM-SHA-256 auth.

**Multi-tenancy:** non-null `tenant_id` column on every PHI/staff/audit row, application-level scoping via a `current_tenant_id` context variable, dedicated cross-tenant isolation tests. Pattern ported from `smart-care-ai`.

**Tenant lifecycle:** gated state machine — `sandbox` → `pending_activation` → `active` → `suspended` → `terminated`. Sandbox tenants are blocked at the application layer from writing PHI; activation requires BAA + identity verification.

**Auth:** PIN + facility code → Argon2id → short-lived JWT (HS256, 8h TTL), with per-user account lockout (5/15min) and a `tokens_invalid_after` revocation timestamp. SSO (SAML/OIDC) deferred to Q3 2026 but the JWT model is designed for additional issuers.

**Deployment:** GKE primary, Cloud SQL for PostgreSQL, Google Secret Manager via External Secrets Operator, GCS for object storage. Helm chart structured so AKS becomes a values-file overlay later. Region pinning via a `region_code` column from day one.

**AI:** Gemini via google-genai, behind a thin `LLMClient` interface so other providers can be added per feature without touching feature code. Versioned prompt files with a golden-output evaluation suite.

## Consequences

**Enables:**

- Both predecessor apps continue to run in production unchanged during the migration. Zero pressure to ship a half-merged thing.
- The unified data model and unified permission model are designed once, deliberately, rather than reconciled under deadline pressure.
- The PHI gate makes self-serve signup safe — anyone can create a sandbox tenant; only verified facilities cross the gate to real PHI. This is what makes the June launch achievable without compromising HIPAA posture.
- The two-schema pattern keeps platform-admin code from accidentally becoming a path to read tenant clinical data, and vice versa.
- GCP-only initial deployment means one Google BAA covers Gemini, Cloud SQL, GKE, and GCS — much simpler legal pass than a multi-cloud first deployment.

**Forecloses (until explicitly revisited):**

- A Node-end-to-end stack. We're committing to Python on the backend; rewriting later would be costly.
- A monorepo workspace tool (Turborepo/Nx). The `apps/`, `services/`, `packages/` folder layout is shaped so promotion to a true workspace is mechanical if we need it, but we don't have it now.
- HL7 v2 support. We expose FHIR R4 only.
- Native mobile apps. The web app must be tablet-first.

**New work this creates:**

- Alembic must be properly initialized from day one — no SQLite ALTER TABLE shortcuts.
- `LLMClient` abstraction layer (small but real).
- `tenant.state`-aware write guards for every PHI-bearing model.
- A cross-service shared package (`nexus-care-db`) so models aren't duplicated across `services/api` and `services/platform`.
- A separate platform-admin service (`services/platform`) with its own auth, separate from the clinician-facing API.

**Ongoing cost:**

- Maintaining the comparison/feature-matrix (`docs/migration/feature-matrix.md`) until the migration is complete.
- The two-old-apps-still-running window — during the migration, three codebases need attention. The phased plan keeps this window short (Phases 1–6 are scoped to ~4 months).

## Alternatives considered

**Merge `smart-care-ai` into `NexusLTC`.** Would force us to keep NexusLTC's unsafe auth and add tenancy retroactively to ~25 Express handlers. Hard pass on security grounds.

**Merge `NexusLTC` into `smart-care-ai`.** Inherits smart-care-ai's flat data model and SQLite migration shortcuts, both of which would have to be redone for a real product. Half the work of a fresh scaffold for two-thirds of the gain.

**Monorepo workspace from day one.** Useful when we need to keep multiple distinct apps around (e.g., admin + clinician + marketing). We have one app right now. Promoting to a workspace later is mechanical; the folder layout is shaped for it.

**Node end-to-end (Express or Fastify backend).** Would let us share types directly with the frontend and reuse NexusLTC's route handlers. Loses smart-care-ai's mature Python AI integration, tested auth, and tenancy isolation tests. The AI features are the differentiator — keeping them in Python where the ecosystem is strongest is more important than a single-language stack.

**Multi-cloud from day one (GKE + AKS in parallel).** Doubles the BAA and ops surface for no compelling reason in 2026. AKS is a values-file away if a customer requires it.

**bcrypt instead of Argon2id.** Both are acceptable. OWASP recommends Argon2id for new systems. Since we're greenfield with no migration cost, we take the modern recommendation.

**Skip the gated-tenant-state pattern; use a simpler "is_demo" flag.** The flag works for demo data but doesn't model the activation flow and doesn't give us a clean place to anchor the BAA artifact, identity verification, and billing. The state machine is more code but it's a small amount more, and it pays for itself the first time a customer asks "what state is my account in?".

**Sales-led only (no self-serve sandbox).** Considered, since most healthcare SaaS goes this route. Rejected because (a) a self-serve sandbox is a strong marketing/demo tool with effectively no compliance risk if PHI writes are blocked, and (b) the gated-state pattern lets us have both — sandbox is self-serve, real PHI is not.

## References

- `ARCHITECTURE.md` — current high-level overview
- `docs/migration/feature-matrix.md` — feature inventory across both predecessor repos
- OWASP Password Storage Cheat Sheet (Argon2id recommendation)
- HIPAA Security Rule, 45 CFR §164.308–§164.316
- Predecessor repos: `github.com/alpfr/smart-care-ai`, `github.com/alpfr/NexusLTC`
