# Feature Matrix — smart-care-ai + NexusLTC → nexus-care-ai

The single source of truth for what's being consolidated. Every feature in either predecessor repo gets a row here with a disposition.

**Last updated:** 2026-05-01 (initial inventory based on repo inspection)

## Disposition codes

- **`take A`** — port from `smart-care-ai` essentially as-is (refactor for new structure)
- **`take N`** — port from `NexusLTC` essentially as-is
- **`merge`** — synthesize a unified version from both, taking the best of each
- **`new`** — exists in only one repo, port whole-cloth
- **`drop`** — won't make it into the new product (placeholder, deprecated, or duplicate)
- **`defer`** — out of scope for initial launch; revisit later

---

## Authentication & Authorization

| Concern | smart-care-ai | NexusLTC | Disposition | Notes |
|---|---|---|---|---|
| PIN + facility code login | ✅ production | ⚠️ accepts any PIN ≥4 chars | **take A** | Foundation for all auth. NexusLTC version is unsafe to ship. |
| Password hashing | bcrypt | none | **upgrade** | Take A's pattern, swap bcrypt for **Argon2id**. |
| JWT issuance | HS256, 8h TTL | unsigned base64 ❌ | **take A** | NexusLTC's "tokens" are not real tokens. |
| Account lockout (5/15min) | ✅ | ❌ | **take A** | |
| Token revocation timestamp | ✅ | ❌ | **take A** | |
| Role model | nurse / supervisor | nurse / med-tech / caregiver / supervisor | **merge** | Use NexusLTC's richer role set; expand A's enforcement. |
| `can(user, action, resource)` helper | partial | ad-hoc role checks in each handler | **new** | Build properly during port. |
| SSO (SAML/OIDC) | ❌ | ❌ | **defer** | Q3 2026. |
| MFA | ❌ | ❌ | **defer** | Q3 2026. |

## Multi-tenancy

| Concern | smart-care-ai | NexusLTC | Disposition | Notes |
|---|---|---|---|---|
| `tenant_id` on every PHI table | ✅ | ❌ | **take A** | Apply pattern to all NexusLTC-derived tables. |
| Tenant scoping middleware | ✅ | ❌ | **take A** | |
| Cross-tenant isolation tests | ✅ 15 tests | ❌ | **take A + extend** | Add tests for every NexusLTC-ported model. |
| `/api/platform/tenants` onboarding | ✅ basic | ❌ | **take A + expand** | Becomes the SaaS platform service. |
| Tenant lifecycle states | ❌ | ❌ | **new** | Gated state machine: sandbox → pending → active → suspended → terminated. |

## Residents (core demographics)

| Concern | smart-care-ai | NexusLTC | Disposition | Notes |
|---|---|---|---|---|
| `Resident` table | flat | normalized + FHIR-aligned | **take N** | NexusLTC's schema is the right one. |
| Separate `resident_name` | ❌ | ✅ | **take N** | Multiple use types (legal, preferred, alias). |
| Separate `resident_identifier` | ❌ | ✅ | **take N** | MRN, MBI, others. |
| Provenance tracking | implicit | ✅ explicit `provenance` table | **take N** | FHIR R4 alignment. |
| DNR status, fall risk, allergies | flat columns | normalized | **take N** | |
| Soft-delete | ✅ | mixed | **take A pattern, apply to N schema** | Soft-delete by default for PHI. |

## Medications & eMAR

| Concern | smart-care-ai | NexusLTC | Disposition | Notes |
|---|---|---|---|---|
| `medication`, `medication_order` tables | basic | ✅ rich | **take N** | |
| Med-pass UI (administer/omit/refuse) | ❌ | ✅ | **take N** | |
| Med reconciliation | ❌ | ✅ | **take N** | |
| PIN re-verify on med signature | ❌ | ✅ | **take N** | |
| Audit_Log entry per med event | partial | ✅ entity_type='MED_PASS' | **take N** | |

## Clinical documentation

| Concern | smart-care-ai | NexusLTC | Disposition | Notes |
|---|---|---|---|---|
| Voice dictation → SOAP (Gemini) | ✅ | UI shell only | **take A** | Big differentiator. |
| Free-text clinical note | ✅ | ✅ | **merge** | A's AI flow + N's structure. |
| CNA shift summary form | ❌ | ✅ | **take N** | |
| Incident report form | ❌ | ✅ | **take N** | |
| Care plan update form | ❌ | ✅ | **take N** | |

## MDS 3.0 / ADL / Care plans / Orders / Vitals — LTC compliance core

| Concern | smart-care-ai | NexusLTC | Disposition | Notes |
|---|---|---|---|---|
| MDS 3.0 forms (A, C/D, G/GG) | ❌ | ✅ | **take N** | Required for Medicare-certified SNFs. |
| `mds_assessment` / `mds_cognitive` / `mds_functional` | ❌ | ✅ | **take N** | |
| ADL assessments | ❌ | ✅ | **take N** | |
| Care plans (with goals + interventions) | ❌ | ✅ | **take N** | Ports as a unit. |
| Physician orders | ❌ | ✅ | **take N** | |
| Vital signs | ❌ | ✅ | **take N** | |
| Consent + rights acknowledgment | ❌ | ✅ | **take N** | |
| Retention policies + legal holds | ❌ | ✅ | **take N** | Important for SOC 2 / HIPAA. |
| Document sharing | ❌ | ✅ | **take N** | |
| Medical team contacts + distribution groups | ❌ | ✅ | **take N** | |

## AI features (the differentiator)

| Concern | smart-care-ai | NexusLTC | Disposition | Notes |
|---|---|---|---|---|
| ReAct documentation assistant (tool-calling Gemini) | ✅ | ❌ | **take A** | |
| SafetySight vision AI (wound + safety hazards) | ✅ | UI shell | **take A** | |
| Nutrition Risk Engine (ASPEN criteria) | ✅ | ❌ | **take A** | |
| 30-day readmission risk score | ✅ | ❌ | **take A** | |
| SBAR shift handoff distillation | ✅ | ❌ | **take A** | |
| Predictive staffing | ✅ | ❌ | **take A** | |
| Versioned prompts + golden-output evals | ❌ | ❌ | **new** | Build during port. |
| `LLMClient` abstraction | inline | ❌ | **new** | Thin interface, Gemini default. |

## Audit & observability

| Concern | smart-care-ai | NexusLTC | Disposition | Notes |
|---|---|---|---|---|
| `audit_log` / `audit_trail` | both have it | both have it | **merge** | N's entity-typed model + A's middleware. |
| PHI access middleware | ✅ | partial | **take A** | |
| Structured JSON logs | ✅ | partial | **take A** | Add PHI scrubber. |
| OpenTelemetry traces | ❌ | ❌ | **new** | Phase 5/6. |
| Sentry error tracking | ❌ | ❌ | **new** | Phase 5/6. |

## Interoperability

| Concern | smart-care-ai | NexusLTC | Disposition | Notes |
|---|---|---|---|---|
| FHIR R4 export (DocumentReference) | ✅ | schema-aligned | **take A** | |
| FHIR import | ✅ basic | ❌ | **take A** | |
| HL7 v2 messaging | ❌ | ❌ | **defer / drop** | Out of scope. |
| USCDI v3 alignment | partial | ✅ | **take N (schema)** | |

## Family / external sharing

| Concern | smart-care-ai | NexusLTC | Disposition | Notes |
|---|---|---|---|---|
| Family share-token + summary | ✅ | ❌ | **take A** | |
| Document sharing (clinician → external) | ❌ | ✅ | **take N** | |

## Notifications

| Concern | smart-care-ai | NexusLTC | Disposition | Notes |
|---|---|---|---|---|
| Notification contacts table | ✅ | ✅ | **merge** | |
| SSE event stream | ✅ | ✅ | **take A** | A's implementation is more thorough. |

## Frontend feature modules

| Concern | smart-care-ai | NexusLTC | Disposition | Notes |
|---|---|---|---|---|
| Login screen | ✅ | ✅ | **take N** | NexusLTC's UX is closer to bedside-friendly. |
| Resident dashboard | ✅ | ✅ richer | **take N** | |
| Supervisor portal ("command center") | ✅ critical-path layout | ✅ broader scope | **merge** | |
| Voice record component | ✅ | ✅ shell | **take A backend, N UI** | |
| Wound scan component | ✅ | ✅ shell | **take A backend, N UI** | |
| Theme toggle / dark mode | ✅ | ❌ | **take A** | |
| User guide / about pages | ✅ | ❌ | **take A** | |
| Clinical document forms | ❌ | ✅ multiple | **take N** | |

## Deployment & infra

| Concern | smart-care-ai | NexusLTC | Disposition | Notes |
|---|---|---|---|---|
| Kubernetes manifests | ✅ GKE | ✅ EKS / AKS | **rebuild as Helm** | Single chart, values per cloud. |
| Dockerfile (backend) | Alpine | (Express) | **rebuild** | Switch to slim-bookworm Python. |
| Dockerfile (frontend) | ✅ | ✅ nginx-served | **rebuild** | Standalone Next.js output. |
| docker-compose for local dev | ✅ basic | ❌ | **take A + extend** | Add Postgres + seeded sandbox tenant. |
| GitHub Actions CI | partial | partial | **rebuild** | Lint + test + container scan + deploy. |
| Snyk / Sonar / linter configs | ❌ | ✅ | **take N (configs only)** | |
| SOC 2 doc skeleton | ❌ | ✅ | **take N** | Foundation to build on. |

---

## Open questions (resolve as we go)

- [ ] Which exact MDS 3.0 sections are blocking for first paying customer? (Section A is identifier; G is functional status; full set is large.)
- [ ] What FHIR resources beyond DocumentReference do design partners actually need? (List, Encounter, Observation are likely candidates.)
- [ ] Real PHI today: which tenants/facilities? How many residents? Affects Phase 7 cutover scope.
- [ ] Existing customer commitments (if any) for the June launch?

---

## Update protocol

When you port a feature:

1. Find its row in this matrix.
2. Add the PR link in a `Done` column on the right (add the column when you do the first port).
3. If your port revealed something the matrix got wrong, fix the disposition and explain why in the PR.
4. If the feature is being deferred or dropped, move it to a "Deferred" or "Dropped" section at the bottom rather than deleting the row.
