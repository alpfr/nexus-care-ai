"""JWT issuer and verifier with revocation support.

Tokens are HS256-signed JWTs with an 8-hour TTL. Claims include:

    sub           — user_id (string)
    tenant_id     — int
    tenant_state  — sandbox | pending_activation | active | suspended | terminated
    region        — region_code (e.g., us-central)
    role          — nurse | med_tech | caregiver | supervisor | tenant_admin
    iat           — issued-at timestamp (seconds since epoch)
    exp           — expires-at timestamp
    jti           — random per-token UUID (for future token-blacklist needs)

Revocation is per-user, not per-token: each user has a `tokens_invalid_after`
timestamp in the database. On verify, we compare the token's `iat` against
the user's `tokens_invalid_after`; if `iat <= tokens_invalid_after`, reject.
This lets us invalidate every existing token for a user (lost device, badge
revoked, role change) by bumping one column, with no token-blacklist table
to maintain.

Algorithm choice: HS256 (symmetric) for simplicity in a single-organization
deployment. When we add SSO providers in Q3 2026, we'll add RS256 verification
for SSO-issued tokens while keeping HS256 for our own issuer.

The signing key MUST come from the environment in production — never hardcode.
For local dev a random key generated at startup is fine (see services/api).
"""

from __future__ import annotations

import datetime as dt
import uuid
from dataclasses import dataclass

import jwt as pyjwt
from pydantic import BaseModel, Field

JWT_ALGORITHM = "HS256"
JWT_TTL_SECONDS = 8 * 60 * 60  # 8 hours
JWT_ISSUER = "nexus-care-ai"


class TokenClaims(BaseModel):
    """Public claims contained in a Nexus Care AI JWT.

    Extra fields that JWT libraries set (iss, etc.) are accepted but not
    surfaced. Forbid extras on parse to catch malformed tokens early.
    """

    sub: str
    tenant_id: int
    tenant_state: str
    region: str
    role: str
    iat: int = Field(description="Issued-at, seconds since epoch")
    exp: int = Field(description="Expires-at, seconds since epoch")
    jti: str

    model_config = {"extra": "ignore"}


@dataclass(frozen=True, slots=True)
class IssuedToken:
    """Result of issue_token: the encoded string + the claims that went into it."""

    token: str
    claims: TokenClaims


class InvalidTokenError(Exception):
    """Raised on any token-verification failure: bad signature, expired,
    malformed, or revoked. The caller MUST NOT distinguish causes in error
    messages returned to the client.
    """


def issue_token(
    *,
    user_id: int,
    tenant_id: int,
    tenant_state: str,
    region: str,
    role: str,
    signing_key: str,
    ttl_seconds: int = JWT_TTL_SECONDS,
    now: dt.datetime | None = None,
) -> IssuedToken:
    """Issue a fresh JWT for a successfully-authenticated user.

    `now` is injectable for tests. In production, omit it.
    """
    issued_at = now or dt.datetime.now(dt.UTC)
    iat = int(issued_at.timestamp())
    exp = iat + ttl_seconds
    jti = uuid.uuid4().hex

    claims = TokenClaims(
        sub=str(user_id),
        tenant_id=tenant_id,
        tenant_state=tenant_state,
        region=region,
        role=role,
        iat=iat,
        exp=exp,
        jti=jti,
    )

    payload = {
        **claims.model_dump(),
        "iss": JWT_ISSUER,
    }
    token = pyjwt.encode(payload, signing_key, algorithm=JWT_ALGORITHM)
    return IssuedToken(token=token, claims=claims)


def verify_token(
    token: str,
    *,
    signing_key: str,
    tokens_invalid_after: int | None = None,
) -> TokenClaims:
    """Decode and verify a token. Raises InvalidTokenError on any failure.

    `tokens_invalid_after`, if provided, is a Unix timestamp; tokens issued
    at or before this time are rejected (revocation check). The caller is
    responsible for fetching this value from the user's row in the database
    after decoding `sub`.

    Typical flow:
        1. Call verify_token(token, signing_key=KEY) — gets claims, no DB.
        2. Look up user by claims.sub, read user.tokens_invalid_after.
        3. Call verify_token(token, signing_key=KEY,
                              tokens_invalid_after=user.tokens_invalid_after)
           — same call shape, but now with revocation check.

    The two-step pattern is intentional: it lets us decide whether to incur
    the DB hit (e.g., skip it for low-trust endpoints) without duplicating
    JWT-decoding logic.
    """
    try:
        decoded = pyjwt.decode(
            token,
            signing_key,
            algorithms=[JWT_ALGORITHM],
            issuer=JWT_ISSUER,
            options={"require": ["sub", "tenant_id", "iat", "exp", "jti"]},
        )
    except pyjwt.ExpiredSignatureError as exc:
        raise InvalidTokenError("token expired") from exc
    except pyjwt.InvalidIssuerError as exc:
        raise InvalidTokenError("bad issuer") from exc
    except pyjwt.InvalidTokenError as exc:
        raise InvalidTokenError("invalid token") from exc

    try:
        claims = TokenClaims.model_validate(decoded)
    except Exception as exc:
        raise InvalidTokenError("malformed claims") from exc

    if tokens_invalid_after is not None and claims.iat <= tokens_invalid_after:
        raise InvalidTokenError("token revoked")

    return claims
