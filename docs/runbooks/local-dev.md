# Local Development Runbook

After this runbook: you have Postgres running, the schema migrated, a sandbox tenant seeded, the FastAPI backend serving JSON on port 18001, and the Next.js frontend serving the login screen on port 3001.

## One-time setup

```bash
cd /Users/alpfr/Projects/nexus-care-ai

# Copy the env file. Don't commit .env.
cp .env.example .env

# Install all backend + frontend deps
make install
```

## Daily flow — the four-terminal pattern

You'll typically have four terminal tabs open:

| Tab | Purpose | Command |
|---|---|---|
| 1 | Database | `make db-up` once, leave running in background |
| 2 | API | `make api` — long-running |
| 3 | Frontend | `make web` — long-running |
| 4 | Scratch | smoke tests, migrations, etc. |

### Tab 1 — Database

```bash
make db-up
```

Expected ending: `Postgres is ready on localhost:5433.`

This is one-and-done — the container persists across reboots unless you `make db-down`.

### Tab 4 (yes, do this once before the API runs) — Migrate + seed

```bash
set -a; source .env; set +a
make db-migrate
make db-seed
```

Expected: `Running upgrade -> 0001_initial_schema...` followed by the seed banner with PIN `246810`. Idempotent — safe to run again.

### Tab 2 — API

```bash
cd /Users/alpfr/Projects/nexus-care-ai
set -a; source .env; set +a
make api
```

Expected ending: `Application startup complete.` and `Uvicorn running on http://127.0.0.1:18001`.

**Leave running.** Auto-reloads on Python file changes.

### Tab 3 — Frontend

```bash
cd /Users/alpfr/Projects/nexus-care-ai
make web
```

Expected ending: `▲ Next.js 16.x.x` and `- Local:        http://localhost:3001`.

**Leave running.** Auto-reloads on TypeScript/React file changes.

### Browser — open the app

Open <http://localhost:3001/> in any browser. You should see the Nexus Care AI login screen.

Log in with:
- **Facility code:** `demo-sandbox`
- **PIN:** `246810`

You'll land on the dashboard. The orange banner about being in a sandbox tenant is expected — that's the gated state machine in action.

## Smoke tests

If the UI seems off, isolate which layer is the problem:

```bash
# 1. Database reachable?
docker compose ps              # nexus_care_db should show "Up (healthy)"

# 2. API running?
curl http://localhost:18001/api/health
# expected: {"status":"ok","database":"ok"}

# 3. API → DB authentic round-trip?
curl -X POST http://localhost:18001/api/login \
  -H 'Content-Type: application/json' \
  -d '{"facility_code":"demo-sandbox","pin":"246810"}'
# expected: JSON with access_token

# 4. Frontend serving?
curl -s http://localhost:3001 | head -5
# expected: HTML
```

## Resetting the database

If migrations get tangled or you want a clean slate:

```bash
make db-reset
```

Stops Postgres, deletes all data, brings it back up, runs migrations, re-seeds. ~15 seconds.

## Running tests

```bash
# Unit tests (fast — no DB needed)
make test-fast

# Full backend suite including integration tests
make test

# Frontend e2e (Playwright). Requires API + frontend running.
cd apps/web
bun run test:e2e
```

## Stopping for the day

In the API tab and frontend tab: `Ctrl+C`.

For the database (data persists):
```bash
make db-down
```

Next morning, just `make db-up` again.

## Common errors

**`ERROR: connection refused`** — Postgres isn't running. `make db-up`.

**`Address already in use` on 18001** — old API still running, find it with `lsof -i :18001 -P -n` and kill it.

**Login fails with "Invalid login"** — DB is up but sandbox tenant wasn't seeded, or you typed the PIN wrong. `make db-seed` and try `246810` again.

**`bind: address already in use` on 5433** — another container has 5433. `lsof -i :5433` to find it. If it's a stale `nexus_care_db` container, `docker rm -f nexus_care_db`.

**Frontend shows "Cannot connect to API"** — the frontend's rewrite proxy is pointed at the wrong API URL. Check `NEXT_PUBLIC_API_BASE_URL` in `.env` matches your running API port (default 18001). Restart the frontend after changing `.env`.

**CORS error in browser dev tools** — should not happen because of the rewrite proxy. If it does, your env has `NEXT_PUBLIC_API_BASE_URL` blank, so requests are going directly to FastAPI cross-origin. Set it.

## Rollback

This runbook is non-destructive (apart from `make db-reset` and `make db-down -v`, which the runbook calls out). If something goes wrong, no production state is involved — just `make db-reset` and start over.
