"""Authentication primitives for Nexus Care AI.

Three concerns, three modules:

- pin: Argon2id PIN hashing and verification, with rehashing on parameter upgrades.
- tokens: JWT issuer and verifier with revocation timestamps.
- permissions: the can(user, action, resource) helper.

Nothing in this package talks to a database directly. Database lookups happen
in the services that import this package. This keeps auth easy to test in
isolation and easy to use from any service (clinical API, platform API,
background jobs).
"""

from nexus_care_auth.permissions import can
from nexus_care_auth.pin import (
    PINMismatch,
    hash_pin,
    needs_rehash,
    verify_pin,
)
from nexus_care_auth.tokens import (
    InvalidTokenError,
    TokenClaims,
    issue_token,
    verify_token,
)

__all__ = [
    "InvalidTokenError",
    "PINMismatch",
    "TokenClaims",
    "can",
    "hash_pin",
    "issue_token",
    "needs_rehash",
    "verify_pin",
    "verify_token",
]
