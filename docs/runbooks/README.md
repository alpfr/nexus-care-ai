# Runbooks

Operational procedures. Step-by-step playbooks an operator follows.

| Runbook | Purpose |
|---|---|
| [`local-dev.md`](local-dev.md) | Set up the full stack on your laptop |
| [`deploy-staging.md`](deploy-staging.md) | One-time GCP setup + how to deploy to staging |

Future runbooks (deferred until needed):

- `incident-response.md` — what to do when staging or prod is broken
- `restore-from-backup.md` — Cloud SQL point-in-time recovery
- `rotate-jwt-keys.md` — process for rotating signing keys without forced logout
- `tenant-suspension.md` — operational steps when a customer account is suspended
- `cutover.md` — Phase 10 data migration from `smart-care-ai` and `NexusLTC`
