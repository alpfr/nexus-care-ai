# apps/web

The Next.js 16 frontend for Nexus Care AI.

This directory currently contains **only the package manifest and TypeScript config**. The actual Next.js scaffold (App Router pages, layout, components) lands in **tranche 3** of the migration plan.

## Why empty?

The migration plan builds the system in commit-sized tranches. Tranche 1 (current) sets up the repo skeleton and dependency manifests so `bun install` and `uv sync` produce reproducible environments. The application code follows once the foundation is verified.

## What's planned for this app

- **App Router** with route groups for the three audiences:
  - `(clinician)/` — bedside workflow (residents, eMAR, notes, MDS, ADL, vitals)
  - `(supervisor)/` — facility command center, audit, staff, alerts
  - `(family)/` — read-only summary via share-token
- **Tailwind v4 + shadcn/ui** — copy-in components, no runtime UI dependency
- **TanStack Query** for server cache; **Zustand** for cross-page UI state; **Context** for `auth` and `tenant` only
- **react-hook-form + Zod** for forms — same Zod schemas the backend uses for validation
- **Playwright** for end-to-end role-based tests

See [`../../ARCHITECTURE.md`](../../ARCHITECTURE.md) for the full picture.
