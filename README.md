# Nexus Care AI

An AI-native EHR platform for Post-Acute and Long-Term Care (PALTC).

Nexus Care AI consolidates two predecessor projects (`smart-care-ai` and `NexusLTC`) into a single multi-tenant SaaS product. It pairs a serious PALTC-aligned clinical data model with a first-class AI documentation assistant — voice-driven SOAP generation, SBAR shift handoffs, predictive readmission risk, wound-vision analysis, and nutrition-risk evaluation.

## Status

🚧 **Pre-launch.** The codebase is being scaffolded. Track progress in [`docs/migration/`](docs/migration/).

## What lives where

```
nexus-care-ai/
├── apps/web/             Next.js 16 frontend (clinician + family + admin UI)
├── services/api/         FastAPI backend (clinical + AI + audit)
├── services/platform/    SaaS platform admin (tenants, billing, feature flags)
├── packages/             Internal libraries shared between services
├── db/                   SQLAlchemy schema + Alembic migrations + seed data
├── infra/                Docker, Helm chart, CI workflows
├── docs/                 Architecture docs, ADRs, migration plan, runbooks
├── tests/                Cross-service integration + e2e tests
└── scripts/              One-off utilities
```

Each top-level folder has its own README that explains what's inside.

## Quick start (local dev)

> **Prerequisites:** [`uv`](https://docs.astral.sh/uv/), [`bun`](https://bun.sh/), `docker`, `git`. uv installs Python 3.13 automatically; bun bundles its own Node-compatible runtime.

```bash
git clone https://github.com/alpfr/nexus-care-ai.git
cd nexus-care-ai

# Backend dependencies (also installs Python 3.13 inside the project)
uv sync

# Frontend dependencies
cd apps/web && bun install && cd ../..

# (Tranche 5+) Bring up the full local stack
# docker compose up
```

The full local-dev workflow lands in tranche 5 of the migration plan once Docker Compose is wired up. Until then, `uv sync` and `bun install` are enough to validate the repo is well-formed.

## Architecture in one paragraph

A single-app SaaS: **FastAPI backend + Next.js frontend + PostgreSQL 18**. Multi-tenancy is enforced by a `tenant_id` column on every PHI/staff row, with row-level filtering in the data layer and dedicated isolation tests. Auth is PIN + facility code → Argon2id-hashed → short-lived JWT, with account lockout and token revocation. Tenants progress through a gated state machine — `sandbox` → `pending_activation` → `active` — so synthetic-data exploration is self-serve while real PHI is gated behind BAA + identity verification. AI features call Google Gemini through a thin `LLMClient` interface that keeps the door open for other providers later. See [`ARCHITECTURE.md`](ARCHITECTURE.md) for the full picture and [`docs/adr/`](docs/adr/) for the decisions behind it.

## Documentation map

| Doc | Purpose |
|---|---|
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | Big-picture architecture, kept current |
| [`CONTRIBUTING.md`](CONTRIBUTING.md) | How to work in this repo |
| [`docs/adr/`](docs/adr/) | Why we made each major decision |
| [`docs/migration/`](docs/migration/) | The consolidation plan and feature inventory |
| [`docs/runbooks/`](docs/runbooks/) | Operational playbooks (deploys, incidents, cutover) |

## License

Proprietary. All rights reserved.
