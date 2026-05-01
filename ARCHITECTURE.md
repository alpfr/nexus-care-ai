# Architecture

This is the living architectural overview for Nexus Care AI. It describes what we're building, the major decisions, and the boundaries between components. It's kept short on purpose — when something changes, we update this doc, and we record *why* in [`docs/adr/`](docs/adr/).

## What we're building

A multi-tenant SaaS EHR for Post-Acute and Long-Term Care facilities. The product has two distinguishing positions in the market:

1. **AI-native, not AI-bolted-on.** Voice-driven SOAP generation, SBAR shift handoffs, 30-day readmission risk scoring, wound-vision analysis, and ASPEN-criteria nutrition-risk evaluation are built into the core workflow rather than added as side features.
2. **Mobile-first bedside UX.** The product is designed to be the EHR nurses actually want to use during med-pass — fast, thumb-friendly, voice-first.

It must also match the incumbents on the table-stakes that LTC facilities cannot live without: MDS 3.0 submissions, eMAR with administer/omit/refuse flow, care plans with goals and interventions, physician orders, ADL assessments, vital signs, consent and rights acknowledgment, retention policies, FHIR R4 export, and a billing-grade audit trail.

## High-level diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                            Browser                                  │
│         (clinician tablet / supervisor desktop / family link)       │
└────────────────────────────────┬────────────────────────────────────┘
                                 │  HTTPS
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│                       apps/web (Next.js 16)                         │
│   App Router · React 19 · Tailwind v4 + shadcn/ui · TanStack Query  │
└──────────────────┬───────────────────────────────┬──────────────────┘
                   │                               │
                   │  /api/*                       │  /api/platform/*
                   ▼                               ▼
┌──────────────────────────────┐   ┌──────────────────────────────────┐
│   services/api (FastAPI)     │   │  services/platform (FastAPI)     │
│   Tenant-scoped clinical +   │   │  Tenant lifecycle, billing,      │
│   AI endpoints. Argon2id PIN │   │  feature flags, BAA artifacts.   │
│   + JWT auth. Tenant guard   │   │  Platform-admin auth.            │
│   on every request.          │   │                                  │
└──────────────────┬───────────┘   └────────────┬─────────────────────┘
                   │                            │
                   │      packages/* (shared)   │
                   │                            │
                   ▼                            ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    PostgreSQL 18 (Cloud SQL)                        │
│   schema=tenant_data : residents, meds, notes, audit, ...           │
│   schema=platform    : tenants, feature_flags, baa_artifacts, ...   │
└─────────────────────────────────────────────────────────────────────┘
                   │                            │
                   ▼                            ▼
        ┌────────────────────┐       ┌──────────────────────┐
        │  Google Gemini     │       │  Object storage      │
        │  (via google-genai │       │  (voice, wound imgs, │
        │  behind LLMClient) │       │  consent PDFs)       │
        └────────────────────┘       └──────────────────────┘
```

## Stack at a glance

| Layer | Technology | Pin |
|---|---|---|
| Frontend framework | Next.js (App Router, Turbopack, React Compiler) | 16.2 |
| UI runtime | React | 19.2 |
| Styling | Tailwind CSS + shadcn/ui | v4 / latest |
| Server-state cache | TanStack Query | latest |
| Forms | react-hook-form + Zod | latest |
| UI state | Zustand (cross-page) + Context (auth/tenant) | latest |
| Frontend tests | Vitest + Testing Library + Playwright (e2e) | latest |
| Backend framework | FastAPI | 0.136.x |
| Backend runtime | Python | 3.13 |
| ORM | SQLAlchemy (typed Mapped style) | 2.0.x |
| Migrations | Alembic | latest |
| Validation | Pydantic v2 | 2.13.x |
| Password hashing | argon2-cffi (Argon2id) | latest |
| Tokens | PyJWT (HS256, short TTL) | latest |
| Linter/formatter (Py) | Ruff | latest |
| Backend tests | pytest + pytest-asyncio + httpx | latest |
| Database | PostgreSQL | 18.3 |
| AI / LLM | Google Gemini via google-genai | 1.46+ |
| Containers | Docker (slim-bookworm Python, node:22-alpine) | — |
| Orchestration | Helm chart, GKE primary | — |
| Secrets | External Secrets Operator + Google Secret Manager | — |
| Observability | OpenTelemetry traces + Sentry + JSON stdout logs | — |
| Package mgr (Py) | uv | latest |
| Package mgr (JS) | bun (also works as runtime) | 1.x |

## Data and tenancy model

Every PHI/staff/audit row carries a non-null `tenant_id`. The pattern is enforced three ways:

1. **Column-level:** `tenant_id INTEGER NOT NULL` with a foreign key to `platform.tenants`.
2. **Application-level:** a `current_tenant_id` context variable resolved from the JWT, with all SQLAlchemy queries automatically filtered by it (the `tenancy.scoped()` helper, ported from `smart-care-ai`).
3. **Test-level:** dedicated isolation tests in `tests/integration/test_tenant_isolation.py` that fail loudly if a query forgets to filter on tenant.

Two database schemas live in one Postgres database:

- **`platform`** — tenants, billing subscriptions, feature flags, BAA artifacts, identity verifications, platform admin users. Read/written only by `services/platform`.
- **`tenant_data`** — residents, medications, clinical notes, audit logs, etc. Read/written only by `services/api`. Every row has `tenant_id`.

Cross-schema reads from `tenant_data` to `platform` are limited to the tenant lookup needed for the per-request guard. There are no cross-schema writes.

### Gated tenant-state machine

Every tenant has a `state` field that gates what the tenant can do:

```
  signup        identity+BAA          contract end
  ────►         ────────────►         ────────────►
sandbox  →  pending_activation  →  active  →  suspended  →  terminated
                                      ▲                         │
                                      └─────── reactivate ──────┘
```

- **`sandbox`** — synthetic data only. PHI write paths are blocked at the application layer (and audited if attempted). All AI features run, but against fake data with `mode=sandbox` so logs and traces stay clear of real PHI.
- **`pending_activation`** — tenant has submitted business identity and is awaiting BAA execution + identity verification. Still no PHI writes.
- **`active`** — BAA signed and stored, identity verified, billing in place. PHI writes unlocked.
- **`suspended`** — read-only (e.g., past-due). Retention timer running.
- **`terminated`** — fully deactivated; data retained per policy then deleted.

The state at the time of every PHI write is recorded in the audit log so the boundary is defensible later.

## Authentication and authorization

- **PIN + facility code → Argon2id verification → short-lived JWT (HS256, 8h TTL).**
- PINs are 6 digits, unique within a tenant. Two tenants can legitimately have the same PIN.
- Account lockout: 5 failed attempts → 15-minute lock.
- Token revocation: every user has a `tokens_invalid_after` timestamp; tokens issued before it are rejected. Used for badge revocation, lost device, etc.
- Role model (initial): `nurse`, `med_tech`, `caregiver`, `supervisor`, `tenant_admin`, plus the separate `platform_admin` for the platform service.
- Permissions checked through a single `can(user, action, resource)` helper. No direct role-string checks scattered through handlers.
- SSO (SAML/OIDC) and MFA are deferred to Q3 2026; the JWT model is designed so SSO drops in as an additional issuer without changing downstream code.

## AI features

All AI calls go through a single `LLMClient` interface. The default implementation calls Google Gemini via the `google-genai` SDK; the interface keeps the door open to add Claude, on-prem models for de-identification, etc. Per-tenant rate limits and cost meters wrap the interface so a runaway tenant cannot blow up the AI bill or starve neighbors.

Prompts live in versioned files under `services/api/ai/prompts/` and are exercised by a golden-output evaluation suite under `services/api/ai/evals/`. Changing a prompt requires the eval suite to pass.

## Deployment topology

- **Primary:** GKE (Google Kubernetes Engine), `us-central1` initially. GKE is chosen because Gemini is in GCP (no cross-cloud egress for AI), and a single Google BAA covers GKE, Cloud SQL, GCS, and Gemini.
- **Database:** Cloud SQL for PostgreSQL 18, regional HA, automated backups, point-in-time recovery.
- **Secrets:** Google Secret Manager, surfaced into pods via External Secrets Operator.
- **Object storage:** Google Cloud Storage with CMEK and uniform bucket-level access.
- **Future:** the Helm chart is structured so AKS (Azure) is a values-file overlay, not a rewrite.
- **Multi-region:** every tenant has a `region_code` from day one (`us-central` initially). Adding `us-east`, `eu-west`, etc. is a Helm deployment + a column value, not an architecture change.

## Compliance posture

- **HIPAA:** Business associate of every customer covered entity. BAAs collected via the activation flow.
- **SOC 2 Type II:** clock starts in Q3 2026, audit target ~Q1 2027.
- **Retention and deletion:** per-tenant retention policy enforced by scheduled jobs in `services/api/jobs/`. Terminated tenants enter a configurable retention window before final deletion.
- **Audit log:** append-only by application convention; replicated to a separate sink with no `DELETE` grants. Every PHI read and write is logged with actor, tenant state at write time, and provenance.

## What's deliberately out of scope (for now)

These are flagged so we don't accidentally creep into them. Each gets its own ADR if/when promoted in scope.

- Native mobile apps (web works on tablets, which covers bedside).
- Real-time voice transcription for free-form conversations (we transcribe discrete dictations only).
- HL7 v2 messaging (FHIR R4 only).
- Pharmacy / lab / imaging integrations (we expose FHIR; integration partners consume it).
- Billing claims processing (we export, partners process).

## Where the deeper detail lives

- **Decisions and rationale:** `docs/adr/`
- **Migration plan from the predecessor repos:** `docs/migration/`
- **Operational playbooks:** `docs/runbooks/`
- **API reference:** auto-generated from FastAPI / OpenAPI at `/api/docs` (dev only)
