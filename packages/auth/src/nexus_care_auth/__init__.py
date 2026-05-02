"""Authentication primitives for Nexus Care AI.

Four concerns, four modules:

- pin: Argon2id PIN hashing for clinical users (6-digit PINs, lower params).
- password: Argon2id password hashing for platform admins (full passwords,
  higher params).
- tokens: JWT issuer and verifier with revocation timestamps.
- permissions: the can(user, action, resource) helper.

Nothing in this package talks to a database directly. Database lookups happen
in the services that import this package.
"""

from nexus_care_auth.password import (
    PasswordMismatch,
    hash_password,
    needs_rehash as password_needs_rehash,
    verify_password,
)
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
    "PasswordMismatch",
    "TokenClaims",
    "can",
    "hash_password",
    "hash_pin",
    "issue_token",
    "needs_rehash",
    "password_needs_rehash",
    "verify_password",
    "verify_pin",
    "verify_token",
]
