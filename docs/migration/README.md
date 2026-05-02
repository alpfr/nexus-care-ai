# Migration plan

The phased plan to consolidate `smart-care-ai` and `NexusLTC` into Nexus Care AI.

**Approach:** scaffold a brand-new app and port features incrementally. Both predecessor apps continue to run in production unchanged until cutover. See [`../adr/0001-initial-stack-and-architecture.md`](../adr/0001-initial-stack-and-architecture.md) for the rationale.

## Phase tracker

| Phase | Description | Status | Target |
|---|---|---|---|
| 0 | Discovery & inventory | ✅ done | — |
| 1 | Repo skeleton & tooling | ✅ done | — |
| 2 | Backend hello-world + auth shell + first migration | ✅ done | — |
| 3 | Frontend hello-world + auth shell | ✅ done | — |
| 4 | SaaS-platform stub (tenant lifecycle, feature flags) | ✅ done | — |
| 5 | Containers + Helm + CI | ⏳ next | May 2026, end |
| 6 | Core LTC features (residents, eMAR, MDS, ADL, care plans, vitals) | ⏳ | June 2026 |
| 7 | AI features (SOAP, SBAR, wound vision, nutrition risk, predictive staffing) | ⏳ | June 2026 |
| 8 | Public sandbox launch + design-partner onboarding | ⏳ | end of June 2026 |
| 9 | SOC 2 prep + activation flow + billing | ⏳ | Q3 2026 |
| 10 | Data cutover from predecessor apps + decommission | ⏳ | Q3–Q4 2026 |
| 11 | General availability | ⏳ | Q1 2027 |

## How phases work

Each phase is sized so it's completable and demoable in **about a week** of focused work. Each phase has:

- A clear objective
- A list of files/systems involved
- An explicit validation gate before the next phase starts
- A rollback plan that doesn't break what came before

Phases are commit-sized. A phase ends with a green CI on `main` and a tag.

## Validation gates

Before any phase is marked done:

1. CI must be green on `main`.
2. The new functionality must work end-to-end in staging (or local-dev for early phases).
3. The relevant tests must exist and pass (unit + integration + e2e where applicable).
4. The phase's checklist in this folder must all be ticked.

## Documents in this folder

- [`feature-matrix.md`](feature-matrix.md) — every feature in either predecessor with a disposition (port / merge / drop / defer).
- `port-log.md` — chronological log of what was ported, when, from which repo (created in Phase 6).
- `cutover-runbook.md` — step-by-step plan for Phase 10 (created in Phase 8).
