"""Nexus Care Platform — SaaS admin service.

Composition root. Run via:

    uv run fastapi dev services/platform/src/nexus_care_platform/app.py --port 18002
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from nexus_care_platform.routes import auth, feature_flags, health, tenants
from nexus_care_platform.settings import get_settings


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="Nexus Care Platform",
        version="0.1.0",
        description=(
            "SaaS platform admin service for Nexus Care AI. "
            "Tenant lifecycle, feature flags, and (future) billing."
        ),
        docs_url=("/api/platform/docs" if settings.environment == "development" else None),
        redoc_url=None,
        openapi_url=(
            "/api/platform/openapi.json" if settings.environment == "development" else None
        ),
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.admin_ui_origin],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )

    # All platform routes live under /api/platform/* so a single ingress can
    # path-route platform vs. clinical traffic later.
    app.include_router(health.router, prefix="/api/platform")
    app.include_router(auth.router, prefix="/api/platform")
    app.include_router(tenants.router, prefix="/api/platform")
    app.include_router(feature_flags.router, prefix="/api/platform")

    return app


app = create_app()
