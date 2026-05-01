# infra/

Everything operational. Containers, Kubernetes manifests, CI workflows, and deployment configs.

```
infra/
├── docker/              Dockerfiles + docker-compose for local dev (tranche 5)
├── helm/                Helm chart, with values-gke.yaml and values-aks.yaml (tranche 5)
└── ci/                  GitHub Actions workflows (tranche 5)
```

Currently empty — all of this lands in **tranche 5** of the migration plan, after the application code is in place and we know what we're packaging.

## Conventions

- One Helm chart for the whole product. Cloud differences are values overlays, not separate charts.
- One Dockerfile per deployable. Multi-stage builds. Slim base images.
- All secrets via External Secrets Operator → Google Secret Manager. **No** secrets in values files.
- CI runs on every PR and on push to `main`. Lint + typecheck + test + container scan + (on `main`) deploy to staging.
- Production deploys are manual approval, never auto on merge.
