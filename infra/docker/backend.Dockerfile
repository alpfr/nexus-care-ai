# Nexus Care AI — backend Docker image (clinical API + platform API).
#
# One image with both services baked in; the entrypoint script picks which
# one to run based on the SERVICE env var (api | platform). This keeps the
# Helm chart simple and avoids duplicate image builds for what is, code-wise,
# the same workspace.
#
# Build (from repo root):
#     docker build -f infra/docker/backend.Dockerfile -t nexus-care-backend:dev .
#
# Run clinical API:
#     docker run --rm -p 18001:8000 \
#         -e SERVICE=api -e DATABASE_URL=postgresql+psycopg://... \
#         nexus-care-backend:dev
#
# Migrations are run by a separate Job in Kubernetes (see Helm chart) using
# this same image with SERVICE=migrate.

# ============================================================================
# Stage 1: builder — install dependencies into a virtualenv with uv
# ============================================================================
# IMPORTANT: we build the venv at /app/.venv (the same path it will live at
# in the runtime stage) so shebangs in console scripts (alembic, uvicorn)
# remain valid after the COPY across stages. If we built at /build/.venv
# and copied to /app/.venv, the shebangs would still point at /build/.venv
# and the scripts would silently fail with "exec format error" or
# "required file not found".
FROM python:3.13-slim-bookworm AS builder

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

# Install uv (Astral) — copy from the official slim image.
COPY --from=ghcr.io/astral-sh/uv:0.10.2 /uv /uvx /usr/local/bin/

WORKDIR /app

# Build deps that some Python wheels need at compile time. Stripped from
# the final stage; only runtime libs ship.
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
 && rm -rf /var/lib/apt/lists/*

# Copy workspace metadata first so Docker can cache the dep-resolve step
# when only application code changes.
COPY pyproject.toml uv.lock ./
COPY services/api/pyproject.toml services/api/pyproject.toml
COPY services/platform/pyproject.toml services/platform/pyproject.toml
COPY db/pyproject.toml db/pyproject.toml
COPY packages/tenancy/pyproject.toml packages/tenancy/pyproject.toml
COPY packages/auth/pyproject.toml packages/auth/pyproject.toml

# Stub source dirs so uv sync can resolve workspace members.
RUN mkdir -p services/api/src/nexus_care_api \
             services/platform/src/nexus_care_platform \
             db/src/nexus_care_db \
             packages/tenancy/src/nexus_care_tenancy \
             packages/auth/src/nexus_care_auth \
 && touch services/api/src/nexus_care_api/__init__.py \
          services/platform/src/nexus_care_platform/__init__.py \
          db/src/nexus_care_db/__init__.py \
          packages/tenancy/src/nexus_care_tenancy/__init__.py \
          packages/auth/src/nexus_care_auth/__init__.py \
 && touch README.md

# Install runtime deps (no dev deps) into /app/.venv.
RUN uv sync --frozen --no-dev --no-editable --no-install-project

# Bring in actual source and re-install workspace members so they're
# properly compiled into the venv.
COPY services/ services/
COPY packages/ packages/
COPY db/ db/
COPY alembic.ini ./

RUN uv sync --frozen --no-dev --no-editable

# ============================================================================
# Stage 2: runtime — minimal image with just what's needed to run
# ============================================================================
FROM python:3.13-slim-bookworm AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:$PATH" \
    PORT=8000

# Runtime libs only — libpq for psycopg, ca-certificates for HTTPS.
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
        libpq5 \
        ca-certificates \
        curl \
 && rm -rf /var/lib/apt/lists/* \
 && groupadd -r nexus --gid=1000 \
 && useradd -r -g nexus --uid=1000 -m -d /home/nexus nexus

WORKDIR /app

# Copy venv + source from builder. Critically, /app/.venv → /app/.venv
# (same path) so shebangs in console scripts remain valid.
COPY --from=builder --chown=nexus:nexus /app/.venv /app/.venv
COPY --from=builder --chown=nexus:nexus /app/services /app/services
COPY --from=builder --chown=nexus:nexus /app/packages /app/packages
COPY --from=builder --chown=nexus:nexus /app/db /app/db
COPY --from=builder --chown=nexus:nexus /app/alembic.ini /app/alembic.ini

# Entrypoint: dispatch on SERVICE.
COPY --chown=nexus:nexus infra/docker/backend-entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

USER nexus

EXPOSE 8000

# Healthcheck hits the service-appropriate /health endpoint.
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -fsS "http://localhost:${PORT}/api/${SERVICE_HEALTH_PATH:-health}" || exit 1

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
