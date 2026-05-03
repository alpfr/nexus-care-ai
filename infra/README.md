# infra/

Everything operational. Containers, Kubernetes manifests, CI workflows, deployment configs.

```
infra/
├── docker/
│   ├── backend.Dockerfile         multi-stage Python image (api + platform)
│   ├── backend-entrypoint.sh      dispatch entrypoint (SERVICE=api|platform|migrate)
│   └── frontend.Dockerfile        Next.js standalone Node image
├── helm/
│   └── nexus-care/                Helm chart (cloud-agnostic templates)
│       ├── Chart.yaml
│       ├── values.yaml            defaults
│       ├── values-gke-staging.yaml  GKE staging overlay
│       ├── templates/
│       │   ├── _helpers.tpl
│       │   ├── api-deployment.yaml
│       │   ├── platform-deployment.yaml
│       │   ├── web-deployment.yaml
│       │   ├── migrate-job.yaml
│       │   ├── ingress.yaml
│       │   ├── serviceaccount.yaml
│       │   └── NOTES.txt
│       └── .helmignore
└── README.md (this file)
```

CI/CD workflows live at the repo root under `.github/workflows/`:

- `ci.yml` — runs on every PR + push to main: lint, typecheck, tests, build images, Trivy scan, push images on main
- `deploy-staging.yml` — manual `workflow_dispatch`: deploy to staging via Helm

The staging deploy runbook lives at [`../docs/runbooks/deploy-staging.md`](../docs/runbooks/deploy-staging.md).

## Conventions

- One Helm chart for the whole product. Cloud differences are values overlays, not separate charts.
- One Dockerfile per deployable. Multi-stage builds. Slim base images. Non-root user.
- All secrets via existing Kubernetes Secrets (created out-of-band from Google Secret Manager). No secrets in values files.
- CI runs on every PR and on push to main. Lint + typecheck + test + image build + Trivy scan + (on main) image push.
- Production deploys are manual approval. We don't auto-deploy until tranche 8 (after rollback safety nets are in place).
