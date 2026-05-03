#!/usr/bin/env bash
# Nexus Care AI — backend container entrypoint.
# Picks which service to run based on the SERVICE env var.
#
#   SERVICE=api       → uvicorn nexus_care_api.app:app
#   SERVICE=platform  → uvicorn nexus_care_platform.app:app
#   SERVICE=migrate   → alembic upgrade head, then exit
#
# We invoke uvicorn and alembic as Python modules (`python -m ...`) rather
# than via their script wrappers in /app/.venv/bin. The script wrappers have
# baked-in shebangs that can break across image stages or path changes;
# `python -m` is shebang-free and always works.

set -euo pipefail

: "${SERVICE:=api}"
: "${PORT:=8000}"
: "${LOG_LEVEL:=info}"
: "${WORKERS:=2}"

PYTHON="/app/.venv/bin/python"

case "$SERVICE" in
  api)
    export SERVICE_HEALTH_PATH=health
    exec "$PYTHON" -m uvicorn nexus_care_api.app:app \
        --host 0.0.0.0 \
        --port "$PORT" \
        --workers "$WORKERS" \
        --log-level "$LOG_LEVEL" \
        --proxy-headers \
        --forwarded-allow-ips='*'
    ;;
  platform)
    export SERVICE_HEALTH_PATH=platform/health
    exec "$PYTHON" -m uvicorn nexus_care_platform.app:app \
        --host 0.0.0.0 \
        --port "$PORT" \
        --workers "$WORKERS" \
        --log-level "$LOG_LEVEL" \
        --proxy-headers \
        --forwarded-allow-ips='*'
    ;;
  migrate)
    echo "[entrypoint] Running Alembic migrations..."
    exec "$PYTHON" -m alembic upgrade head
    ;;
  *)
    echo "ERROR: Unknown SERVICE='$SERVICE'. Expected: api | platform | migrate" >&2
    exit 64
    ;;
esac
