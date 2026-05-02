# Local Development Runbook

After this runbook: Postgres running, schemas migrated (now including the platform-admin tables), a sandbox tenant seeded, a platform-admin bootstrapped, FastAPI clinical API on **18001**, FastAPI platform API on **18002**, Next.js frontend on **3001**.

## One-time setup

```bash
cd /Users/alpfr/Projects/nexus-care-ai
cp .env.example .env
make install
```

## Daily flow — five-terminal pattern

| Tab | Purpose | Command |
|---|---|---|
| 1 | Database | `make db-up` once, leave running |
| 2 | Clinical API | `make api` — long-running |
| 3 | Platform API | `make platform` — long-running |
| 4 | Frontend | `make web` — long-running |
| 5 | Scratch | curls, migrations, etc. |

### First-time setup of admin + sandbox

In tab 5:

```bash
set -a; source .env; set +a
make db-migrate
make db-seed
make platform-bootstrap-admin
```

The seed creates a sandbox tenant + supervisor (PIN `246810`). The bootstrap creates a platform admin (`admin@local` / `change-me-locally`).

### Tab 2 — Clinical API

```bash
cd /Users/alpfr/Projects/nexus-care-ai
set -a; source .env; set +a
lsof -ti :18001 | xargs kill -9 2>/dev/null; sleep 1
make api
```

Wait for `Application startup complete.` Leave running.

### Tab 3 — Platform API

```bash
cd /Users/alpfr/Projects/nexus-care-ai
set -a; source .env; set +a
lsof -ti :18002 | xargs kill -9 2>/dev/null; sleep 1
make platform
```

Wait for `Application startup complete.` Leave running.

### Tab 4 — Frontend

```bash
cd /Users/alpfr/Projects/nexus-care-ai/apps/web
bun run dev
```

Open `http://localhost:3001` in your browser. Log in with `demo-sandbox` / `246810`.

## Demo: the activation flow round-trip

This is the new visible behavior in tranche 4.

1. **Log into the dashboard as the supervisor** (`demo-sandbox` / `246810`). Tenant state shows **sandbox** with the orange banner.
2. **Click "Request activation"** in the banner. The mutation hits `POST /api/me/tenant/request-activation`. State transitions to `pending_activation`. The banner changes to a teal "Activation pending review."
3. **In tab 5, log in as the platform admin via curl:**

```bash
ADM_TOKEN=$(curl -s -X POST http://localhost:18002/api/platform/admin/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"admin@local","password":"change-me-locally"}' \
  | python3 -c "import sys,json;print(json.load(sys.stdin)['access_token'])")
echo "$ADM_TOKEN"
```

4. **List tenants — should show the sandbox tenant in pending_activation:**

```bash
curl -s http://localhost:18002/api/platform/tenants \
  -H "Authorization: Bearer $ADM_TOKEN" | python3 -m json.tool
```

5. **Approve activation** (tenant id is usually 1 — adjust if you've reset the DB and have multiple tenants):

```bash
curl -s -X PATCH http://localhost:18002/api/platform/tenants/1/state \
  -H 'Content-Type: application/json' \
  -H "Authorization: Bearer $ADM_TOKEN" \
  -d '{
    "target_state": "active",
    "baa_artifact_ref": "docusign:test:abc",
    "identity_verification_ref": "persona:test:xyz"
  }' | python3 -m json.tool
```

6. **Refresh the dashboard in your browser.** The banner changes from teal "pending review" to green "Tenant is active." That round-trip — supervisor request → admin approve → UI reflects state — is the entire SaaS gate in action.

## Verify bright-line auth separation

The most important security property of the split: clinical tokens cannot do platform actions, and vice versa. Verify with curl:

```bash
SUP_TOKEN=$(curl -s -X POST http://localhost:18001/api/login \
  -H 'Content-Type: application/json' \
  -d '{"facility_code":"demo-sandbox","pin":"246810"}' \
  | python3 -c "import sys,json;print(json.load(sys.stdin)['access_token'])")

curl -i http://localhost:18002/api/platform/tenants \
  -H "Authorization: Bearer $SUP_TOKEN"
```

Expected: `HTTP/1.1 401 Unauthorized` — clinical token rejected by platform service.

```bash
curl -i http://localhost:18001/api/me \
  -H "Authorization: Bearer $ADM_TOKEN"
```

Expected: `HTTP/1.1 401 Unauthorized` — platform token rejected by clinical service.

If either of those returns 200, **stop and tell me immediately** — the bright line is broken.

## Resetting

```bash
make db-reset
```

Drops all data, brings Postgres back up, migrates, seeds the sandbox, bootstraps the platform admin. ~20 seconds.

## Common errors

**`401` from `/api/platform/admin/login`** — bad credentials. Default is `admin@local` / `change-me-locally`. Change with `bootstrap_platform_admin.py` if needed.

**`409 Illegal transition`** — the state machine rejected your move. Read the response detail; it lists legal targets.

**`422` requiring `baa_artifact_ref`** — activation requires both the BAA reference and the identity-verification reference. Pass both.

**`Address already in use` on 18002** — old platform API running. `lsof -ti :18002 | xargs kill -9`.

**Frontend "Request activation" button does nothing** — check browser dev tools Network tab. If the request is hitting the wrong port, your `NEXT_PUBLIC_API_BASE_URL` is stale; restart `bun run dev` after editing `.env`.

## Rollback

Non-destructive (apart from `make db-reset` and `docker compose down -v`). If anything goes sideways, `make db-reset` and start over.
