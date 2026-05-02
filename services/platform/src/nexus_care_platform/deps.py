"""FastAPI deps for the platform service.

Critical bright line: this service uses `nexus_care_auth.password` (passwords)
and a separate JWT signing key from the clinical API. A clinical PIN-derived
JWT cannot authenticate against the platform service even if it leaked.
"""

from __future__ import annotations

from collections.abc import Generator
from dataclasses import dataclass
from functools import lru_cache

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session, sessionmaker

from nexus_care_auth import InvalidTokenError, verify_token
from nexus_care_db import PlatformAdmin
from nexus_care_db.session import make_engine, make_session_factory

from nexus_care_platform.settings import Settings, get_settings


@lru_cache(maxsize=1)
def _get_session_factory() -> sessionmaker[Session]:
    settings = get_settings()
    engine = make_engine(
        settings.database_url.get_secret_value(),
        echo=settings.sql_echo,
    )
    return make_session_factory(engine)


def get_db() -> Generator[Session, None, None]:
    factory = _get_session_factory()
    session = factory()
    try:
        yield session
    finally:
        session.close()


@dataclass(frozen=True, slots=True)
class AuthenticatedAdmin:
    id: int
    email: str
    full_name: str


def _extract_bearer(authorization: str | None) -> str:
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return parts[1]


def require_admin(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> AuthenticatedAdmin:
    """Require a valid platform-admin Bearer token.

    Different signing key from the clinical API → tokens issued by /api/login
    will fail signature verification here. That's the whole point.
    """
    token = _extract_bearer(authorization)

    # Two-step verify: decode first to get sub, then re-verify with the
    # admin's tokens_invalid_after pulled from DB.
    try:
        claims = verify_token(token, signing_key=settings.jwt_signing_key.get_secret_value())
    except InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None

    # Defense in depth: require role=platform_admin in the claims, even
    # though only the platform service issues these tokens.
    if claims.role != "platform_admin":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    admin = db.get(PlatformAdmin, int(claims.sub))
    if admin is None or not admin.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        verify_token(
            token,
            signing_key=settings.jwt_signing_key.get_secret_value(),
            tokens_invalid_after=admin.tokens_invalid_after,
        )
    except InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None

    return AuthenticatedAdmin(
        id=admin.id,
        email=admin.email,
        full_name=admin.full_name,
    )
