# Staging Deploy Runbook

After this runbook: you have a staging environment on GKE, you can deploy a fresh build to it from GitHub Actions with one click, and you know how to roll back.

## When to use this

- After a merge to `main` lands changes you want to validate in a real environment
- When demoing to a design partner or internal stakeholder
- To sanity-check a release before promoting it elsewhere

This is intentionally manual (per ADR-0001 / tranche 5). Auto-deploy on merge is a tranche-8 enhancement.

## One-time GCP setup

These steps create everything CI needs to deploy. **Do them once per project.** If you've already done them and just want to deploy, skip to "How to deploy."

### 1. Enable APIs

```bash
gcloud config set project alpfr-splunk-integration

gcloud services enable \
  artifactregistry.googleapis.com \
  container.googleapis.com \
  iam.googleapis.com \
  iamcredentials.googleapis.com \
  sqladmin.googleapis.com \
  secretmanager.googleapis.com
```

### 2. Create the Artifact Registry repository

```bash
gcloud artifacts repositories create nexus-care \
  --repository-format=docker \
  --location=us-central1 \
  --description="Nexus Care AI container images"
```

### 3. Create the GKE cluster (staging)

For staging, a small autopilot cluster is plenty:

```bash
gcloud container clusters create-auto nexus-care-staging \
  --region=us-central1 \
  --release-channel=regular
```

This takes 5-10 minutes. It creates the cluster with Workload Identity already enabled (autopilot has it on by default).

### 4. Create a Cloud SQL Postgres instance (staging)

```bash
gcloud sql instances create nexus-care-staging-db \
  --database-version=POSTGRES_18 \
  --region=us-central1 \
  --tier=db-perf-optimized-N-2 \
  --storage-size=20 \
  --backup \
  --enable-point-in-time-recovery
```

Create the database and user (replace the password):

```bash
DB_PASSWORD="$(openssl rand -base64 24)"
echo "Save this password securely: $DB_PASSWORD"

gcloud sql databases create nexus_care \
  --instance=nexus-care-staging-db

gcloud sql users create nexus \
  --instance=nexus-care-staging-db \
  --password="$DB_PASSWORD"
```

### 5. Store secrets in Google Secret Manager

```bash
# Database URL (the connection string our app uses)
DB_URL="postgresql+psycopg://nexus:$DB_PASSWORD@/nexus_care?host=/cloudsql/alpfr-splunk-integration:us-central1:nexus-care-staging-db"
echo -n "$DB_URL" | gcloud secrets create nexus-care-staging-db-url \
  --data-file=- --replication-policy=automatic

# JWT signing keys — DIFFERENT for clinical vs platform (the bright line)
echo -n "$(openssl rand -base64 48)" | gcloud secrets create nexus-care-staging-api-jwt-key \
  --data-file=- --replication-policy=automatic
echo -n "$(openssl rand -base64 48)" | gcloud secrets create nexus-care-staging-platform-jwt-key \
  --data-file=- --replication-policy=automatic
```

### 6. Create the GCP service account for CI (Workload Identity Federation)

```bash
gcloud iam service-accounts create nexus-care-ci \
  --display-name="Nexus Care AI — CI deployer"

# Grant just-enough roles for image push + cluster access.
PROJECT="alpfr-splunk-integration"
SA="nexus-care-ci@${PROJECT}.iam.gserviceaccount.com"

for role in \
  roles/artifactregistry.writer \
  roles/container.developer \
  roles/iam.workloadIdentityUser; do
  gcloud projects add-iam-policy-binding "$PROJECT" \
    --member="serviceAccount:$SA" --role="$role"
done
```

### 7. Set up GitHub OIDC pool

```bash
gcloud iam workload-identity-pools create github \
  --location=global \
  --display-name="GitHub Actions"

gcloud iam workload-identity-pools providers create-oidc github-provider \
  --location=global \
  --workload-identity-pool=github \
  --display-name="GitHub provider" \
  --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository,attribute.repository_owner=assertion.repository_owner" \
  --attribute-condition="attribute.repository_owner == 'alpfr'" \
  --issuer-uri="https://token.actions.githubusercontent.com"
```

Bind the pool to the service account, scoped to your specific repo:

```bash
PROJECT_NUMBER="$(gcloud projects describe $PROJECT --format='value(projectNumber)')"

gcloud iam service-accounts add-iam-policy-binding "$SA" \
  --role=roles/iam.workloadIdentityUser \
  --member="principalSet://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/github/attribute.repository/alpfr/nexus-care-ai"
```

### 8. Add GitHub secrets

In your repo settings → Secrets and variables → Actions → New repository secret. Add:

- `GCP_WORKLOAD_IDENTITY_PROVIDER` = `projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/github/providers/github-provider` (replace `${PROJECT_NUMBER}` with the value from step 7)
- `GCP_CI_SERVICE_ACCOUNT` = `nexus-care-ci@alpfr-splunk-integration.iam.gserviceaccount.com`

### 9. Create the GKE cluster service account (Workload Identity binding)

The pods use a different service account than CI. Create a GCP SA for runtime, bind it to the in-cluster Kubernetes SA via Workload Identity:

```bash
gcloud iam service-accounts create nexus-care-staging \
  --display-name="Nexus Care AI staging — runtime"

# Allow it to read its secrets and connect to Cloud SQL
RUNTIME_SA="nexus-care-staging@${PROJECT}.iam.gserviceaccount.com"
for role in \
  roles/secretmanager.secretAccessor \
  roles/cloudsql.client; do
  gcloud projects add-iam-policy-binding "$PROJECT" \
    --member="serviceAccount:$RUNTIME_SA" --role="$role"
done

# Bind the in-cluster SA (created by Helm) to the GCP SA
gcloud iam service-accounts add-iam-policy-binding "$RUNTIME_SA" \
  --role=roles/iam.workloadIdentityUser \
  --member="serviceAccount:${PROJECT}.svc.id.goog[nexus-care-staging/nexus-care-sa]"
```

### 10. Create Kubernetes Secret with database URL + JWT keys

The Helm chart expects a Secret named `nexus-care-secrets`. For now, create it manually pulling from Secret Manager. (In a fuller setup, External Secrets Operator does this automatically.)

```bash
gcloud container clusters get-credentials nexus-care-staging \
  --location=us-central1 --project="$PROJECT"

kubectl create namespace nexus-care-staging --dry-run=client -o yaml | kubectl apply -f -

DB_URL=$(gcloud secrets versions access latest --secret=nexus-care-staging-db-url)
API_KEY=$(gcloud secrets versions access latest --secret=nexus-care-staging-api-jwt-key)
PLATFORM_KEY=$(gcloud secrets versions access latest --secret=nexus-care-staging-platform-jwt-key)

kubectl -n nexus-care-staging create secret generic nexus-care-secrets \
  --from-literal=database_url="$DB_URL" \
  --from-literal=api_jwt_signing_key="$API_KEY" \
  --from-literal=platform_jwt_signing_key="$PLATFORM_KEY"
```

### 11. Deploy the Cloud SQL Auth Proxy as a sidecar (or set up Private IP)

The simplest staging setup: run the Cloud SQL Auth Proxy as a sidecar in each pod. For now, the easier path is to give the cluster a private IP path to Cloud SQL. The Helm chart's `database.url` value handles either; staging values point the apps at the proxy socket. **You'll likely need to extend the chart to add the sidecar — flag this as a tranche-5b polish item.**

## How to deploy

Once the one-time setup is done, deployments are fast:

### 1. Push your changes to `main`

```bash
git push origin main
```

CI on `main` builds and pushes the container images to Artifact Registry, tagged with the short commit SHA and `latest`.

### 2. Wait for CI to finish

Check <https://github.com/alpfr/nexus-care-ai/actions>. Wait for the CI workflow on `main` to go green. Builds + tests + image push takes ~6-8 minutes.

### 3. Trigger a deploy

Go to **Actions → Deploy (staging) → Run workflow → main → Run workflow**.

Optionally:
- Set **image_tag** to the short SHA of an older commit if you want to deploy something other than the most recent build
- Set **dry_run** to `true` to render manifests without applying (useful for the first run after big chart changes)

### 4. Watch it go

The workflow streams progress. Expected timeline:
- Helm dry-run preview: ~10s
- `helm upgrade --install`: ~3-5 min (waits for pods + ingress to be ready)
- Rollout verify: ~30s

### 5. Smoke-test

```bash
gcloud container clusters get-credentials nexus-care-staging \
  --location=us-central1 --project=alpfr-splunk-integration

kubectl -n nexus-care-staging get pods,svc,ingress

# Get the external IP (it takes a few minutes the first time)
INGRESS_IP=$(kubectl -n nexus-care-staging get ingress nexus-care \
  -o jsonpath='{.status.loadBalancer.ingress[0].ip}')
echo "Ingress IP: $INGRESS_IP"

curl "https://staging.nexus-care.example.com/api/health"
```

Then open the URL in your browser and try logging in.

## Rollback

Helm tracks every release. To roll back the previous one:

```bash
helm -n nexus-care-staging history nexus-care
helm -n nexus-care-staging rollback nexus-care <revision-number>
```

Or, deploy a specific older image tag from the GitHub Actions UI:
- Actions → Deploy (staging) → Run workflow
- Set `image_tag` to the short SHA of the version you want
- Run

Database migrations are forward-only by convention. If a rollback would require schema changes, write a fresh forward migration that fixes the issue.

## Common errors

**`UNAUTHORIZED: failed to get GKE credentials`** — workload identity pool binding is wrong. Verify `GCP_WORKLOAD_IDENTITY_PROVIDER` and `GCP_CI_SERVICE_ACCOUNT` GitHub secrets match what was set up in step 8.

**`Error: failed to download "oci://..."`** — chart wasn't found. Confirm the workflow is checking out the repo at the right path.

**Migrations job fails** — check `kubectl -n nexus-care-staging logs -l app.kubernetes.io/component=migrate --tail=200`. Most likely DATABASE_URL is wrong or the Cloud SQL connection isn't reachable.

**Pods stuck in `ContainerCreating`** — usually image pull issues. `kubectl -n nexus-care-staging describe pod <pod-name>` to see exactly. Often the GKE service account doesn't have `roles/artifactregistry.reader` on the project.

**Ingress shows no IP for >10 min** — the GCE Load Balancer is slow to provision the first time. Patient wait. After 15 min, `kubectl describe ingress` to see if it's stuck on certificate validation.

## What this runbook does NOT cover

- Setting up the **production** environment — same shape, different cluster, different secrets, less tolerance for surprises. Tranche 8 territory.
- Setting up External Secrets Operator — the cleaner way to ferry secrets from GCP Secret Manager into Kubernetes Secrets. Manual `kubectl create secret` works for staging; ESO is the right move once we have multiple secrets to manage.
- Custom monitoring/alerting beyond GCP defaults. Cloud Monitoring catches the basics (pod restarts, ingress 5xx); Sentry + OTEL come in tranche 6+.
