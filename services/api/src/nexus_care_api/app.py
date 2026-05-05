"""Nexus Care API — clinical + AI service.

Composition root. Wires settings, middleware, routers, and exception
handlers into a single FastAPI app. Run via:

    uv run fastapi dev services/api/src/nexus_care_api/app.py
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from nexus_care_tenancy import (
    PHIWriteForbiddenError,
    TenantNotSetError,
)

from nexus_care_api.routes import auth, health, tenant_lifecycle
from nexus_care_api.routes.clinical import (
    medication_orders,
    medications,
    residents,
)
from nexus_care_api.settings import get_settings


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    yield


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="Nexus Care API",
        version="0.1.0",
        description=(
            "Clinical + AI service for Nexus Care AI. Tenant-scoped, PIN+JWT-authenticated."
        ),
        lifespan=_lifespan,
        docs_url="/api/docs" if settings.environment == "development" else None,
        redoc_url=None,
        openapi_url=("/api/openapi.json" if settings.environment == "development" else None),
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_origin],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )

    @app.exception_handler(TenantNotSetError)
    async def _tenant_not_set_handler(_req: Request, _exc: TenantNotSetError):
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Internal error"},
        )

    @app.exception_handler(PHIWriteForbiddenError)
    async def _phi_forbidden_handler(_req: Request, exc: PHIWriteForbiddenError):
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={
                "detail": "PHI writes are not permitted for this tenant in its current state",
                "hint": str(exc),
            },
        )

    # Auth + plumbing
    app.include_router(health.router, prefix="/api")
    app.include_router(auth.router, prefix="/api")
    app.include_router(tenant_lifecycle.router, prefix="/api")

    # Clinical surfaces (tranche 6a)
    app.include_router(residents.router, prefix="/api")
    app.include_router(medications.router, prefix="/api")
    app.include_router(medication_orders.nested_router, prefix="/api")
    app.include_router(medication_orders.flat_router, prefix="/api")

    return app


app = create_app()
