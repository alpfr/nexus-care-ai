# Nexus Care AI — frontend Docker image (Next.js 16, standalone build).
#
# Build (from repo root):
#     docker build -f infra/docker/frontend.Dockerfile \
#         --build-arg NEXT_PUBLIC_API_BASE_URL=https://api.example.com \
#         -t nexus-care-web:dev .
#
# IMPORTANT: NEXT_PUBLIC_* env vars are baked into the Next.js bundle at
# BUILD time, not runtime. The rewrite destination in next.config.ts is
# evaluated when `next build` runs. So we must pass NEXT_PUBLIC_API_BASE_URL
# as a build arg, not just a runtime env. Setting it as a runtime env
# inside docker-compose has no effect on the rewrite — it would only be
# visible to client-side code that explicitly reads
# process.env.NEXT_PUBLIC_*.

# ============================================================================
# Stage 1: deps — install dependencies via bun
# ============================================================================
FROM oven/bun:1.3 AS deps

WORKDIR /build

COPY apps/web/package.json apps/web/bun.lock* ./
RUN bun install --frozen-lockfile 2>/dev/null || bun install

# ============================================================================
# Stage 2: builder — compile the Next.js standalone bundle
# ============================================================================
FROM oven/bun:1.3 AS builder

# Build-time API base URL. Must be set per build target via:
#     --build-arg NEXT_PUBLIC_API_BASE_URL=...
# Default points at the in-cluster api service (works for docker-compose
# 'full' profile where the service name 'api' resolves to the api container).
ARG NEXT_PUBLIC_API_BASE_URL=http://api:8000

WORKDIR /build

ENV NEXT_TELEMETRY_DISABLED=1 \
    NODE_ENV=production \
    NEXT_OUTPUT=standalone \
    NEXT_PUBLIC_API_BASE_URL=${NEXT_PUBLIC_API_BASE_URL}

COPY --from=deps /build/node_modules ./node_modules
COPY apps/web/ ./

RUN bun run build

# ============================================================================
# Stage 3: runtime — minimal Node runtime serving the standalone bundle
# ============================================================================
# node:22-bookworm-slim ships a 'node' user with UID/GID 1000 by default.
# We reuse that rather than create a second user at the same UID.
FROM node:22-bookworm-slim AS runtime

ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0

# Minimal runtime deps. The 'node' user already exists at UID 1000.
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY --from=builder --chown=node:node /build/.next/standalone ./
COPY --from=builder --chown=node:node /build/.next/static ./.next/static
COPY --from=builder --chown=node:node /build/public ./public

USER node

EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -fsS "http://localhost:${PORT}/" || exit 1

CMD ["node", "server.js"]
