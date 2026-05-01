# Contributing

Quick reference for working in this repo. Read [`ARCHITECTURE.md`](ARCHITECTURE.md) for the big picture and [`docs/adr/`](docs/adr/) for the *why* behind decisions.

## Branch model

- **`main`** — always deployable. Direct pushes are blocked; all changes land via PR.
- **Feature branches** — `feat/<short-description>`, branched from `main`.
- **Fixes** — `fix/<short-description>`.
- **Migration / port branches** — `port/<source-repo>/<feature>` (e.g., `port/nexusltc/mds-3.0`).
- **Spike / exploration** — `spike/<short-description>`. Spikes are throwaway by definition; if a spike becomes real work, open a fresh `feat/` branch.

## Commits

[Conventional Commits](https://www.conventionalcommits.org/) format:

```
<type>(<scope>): <short summary>

<body, optional but encouraged for non-trivial changes>
```

Types we use: `feat`, `fix`, `chore`, `docs`, `refactor`, `test`, `perf`, `port`.

Scopes match top-level folders: `api`, `web`, `platform`, `db`, `infra`, `docs`.

Examples:
```
feat(api): add Argon2id PIN hashing module
fix(web): correct tenant-code casing in login form
port(nexusltc): bring MDS Section A across to api
chore(infra): bump postgres image to 18.3
```

## Pull requests

- One logical change per PR. If you find yourself writing "and also" in the description, split it.
- PR description must explain **what** changed and **why**. The diff shows what; the description must show why.
- Link to the ADR if the change touches an architectural decision.
- All PRs require:
  - Green CI (lint, typecheck, tests, container scan)
  - At least one approving review
  - Up-to-date branch (rebase, don't merge `main` in)
- Squash-merge to keep `main` history linear.

## Local checks before pushing

Backend:
```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy services
uv run pytest
```

Frontend:
```bash
cd apps/web
bun run lint
bun run typecheck
bun run test
```

## Architecture Decision Records

When a change shifts a major decision (stack pick, security model, data architecture), add an ADR under `docs/adr/`. Use the template at `docs/adr/0000-template.md`. Don't edit existing ADRs — supersede them with new ones.

## Security

- **Never** commit secrets. The `.gitignore` blocks `.env`, `*.pem`, etc., but it's a backstop. If you commit a secret by accident, treat it as compromised — rotate it, don't just `git revert`.
- **Never** log PHI. Structured logs go through `services/api/src/nexus_care_api/observability.py` (lands in tranche 2), which has a PHI scrubber in front of stdout.
- **Never** disable a tenant-scoped query without an ADR explaining why. The cross-tenant isolation tests are non-negotiable.

## Style notes

- Python: Ruff handles formatting and linting. Don't argue with the formatter.
- TypeScript: Prettier handles formatting. Same.
- File naming: `kebab-case` for files, `PascalCase` for React components, `snake_case` for Python modules.
- Imports: absolute (`from nexus_care_api.auth import ...`) over relative.

## Getting unstuck

- If `uv sync` fails, check that you have `uv` ≥ 0.5 and Python 3.13 isn't broken in the venv (`rm -rf .venv && uv sync`).
- If `bun install` fails, check `node --version` ≥ 22 (Bun bundles its own runtime, but the typings need a recent Node).
- If migrations fail, the local Postgres container is the most likely culprit — `docker compose down -v && docker compose up`.
