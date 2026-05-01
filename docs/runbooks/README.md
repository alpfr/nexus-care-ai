# Runbooks

Operational playbooks live here. A runbook is the document on-call uses at 3am — it must be skimmable, copy-paste-friendly, and assume the reader is tired.

Runbooks land here as we build the systems they cover:

- `local-dev.md` — getting a local dev environment up (Phase 5)
- `deploy-staging.md` — deploying to staging (Phase 5)
- `deploy-production.md` — deploying to production (Phase 8)
- `incident-response.md` — what to do when alerts fire (Phase 8)
- `data-export.md` — exporting a tenant's data (Phase 9)
- `data-deletion.md` — deleting a tenant's data per retention/contract (Phase 9)
- `cutover.md` — predecessor → unified app data migration (Phase 10)

## Runbook style

- **Lead with the outcome:** "After this runbook, X is true."
- **One step per line.** No multi-step paragraphs.
- **Show every command in full.** No "you know, the usual."
- **Show expected output.** So readers know if a step actually worked.
- **Have a rollback section.** Every runbook ends with "if this goes wrong, …".
