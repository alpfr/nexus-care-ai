# Local Development Runbook

After this runbook: you have Postgres running, the schema migrated, a sandbox tenant seeded, and you can hit `/api/login` with a real PIN to get a JWT.

## One-time setup

```bash
cd /Users/alpfr/Projects/nexus-care-ai

# Copy the env file. Don't commit .env.
cp .env.example .env

# Install all backend + frontend deps
make install
```

## Daily flow

```bash
# 1. Start the local Postgres container
make db-up
```

Expected: prints `Postgres is ready on localhost:5433.`

```bash
# 2. Apply migrations (idempotent — safe to run on every start)
make db-migrate
```

Expected: alembic logs `Running upgrade -> 0001_initial_schema`.

```bash
# 3. Seed a sandbox tenant + supervisor user
make db-seed
```

Expected (last lines):

```
============================================================
 Local sandbox is ready. Log in with:
   facility_code: demo-sandbox
   pin:           246810
============================================================
```

```bash
# 4. Start the API in one terminal
make api
```

Expected: uvicorn logs `Application startup complete.` and binds `127.0.0.1:8000`.

In another terminal, smoke-test:

```bash
curl http://localhost:8000/api/health
```

Expected: `{"status":"ok","database":"ok"}`

```bash
# Login. Should return a JWT.
curl -X POST http://localhost:8000/api/login \
  -H 'Content-Type: application/json' \
  -d '{"facility_code":"demo-sandbox","pin":"246810"}'
```

Expected: `{"access_token":"eyJ...","token_type":"bearer","expires_in":28800}`

```bash
# Use the token to hit /api/me. Replace TOKEN_HERE with the access_token value.
curl http://localhost:8000/api/me \
  -H 'Authorization: Bearer TOKEN_HERE'
```

Expected: `{"id":1,"full_name":"Demo Supervisor","role":"supervisor","tenant_id":1,"tenant_state":"sandbox"}`

## Resetting the database

If migrations get tangled or you want a clean slate:

```bash
make db-reset
```

This stops Postgres, **deletes all data**, brings it back up, runs all migrations, and re-seeds. Takes about 15 seconds.

## Running tests

```bash
# Unit tests (fast — no DB needed)
make test-fast

# Full suite including integration tests against the local Postgres
make test
```

Make sure the DB is up and migrated before running the full suite.

## Stopping for the day

```bash
make db-down
```

Data persists. Next morning, just `make db-up` again.

## Common errors

**`ERROR: connection refused`** — Postgres isn't running. `make db-up`.

**`alembic.util.exc.CommandError: Can't locate revision identified by '0001_initial_schema'`** — Your local DB has migration history pointing to a different repo. `make db-reset` or drop and recreate the database.

**`FATAL: password authentication failed`** — Your `.env` `DATABASE_URL` doesn't match the docker-compose creds. Default is `postgresql+psycopg://nexus:nexus@localhost:5433/nexus_care`.

**`bind: address already in use` on port 5433** — Some other process is on 5433. `lsof -i :5433` to find it. If it's a stale `nexus_care_db` container, `docker rm -f nexus_care_db`.

## Rollback

This runbook is non-destructive (apart from `make db-reset` and `make db-down -v`, both of which the runbook calls out explicitly). If something goes wrong, no production state is involved — just `make db-reset` and start over.
