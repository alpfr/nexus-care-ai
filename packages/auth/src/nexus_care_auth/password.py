"""Argon2id password hashing for platform-admin authentication.

Separate from the PIN module because:
  - PINs are 6 digits with a low-entropy threat model; this is full-strength
    user passwords.
  - Different Argon2 parameters are appropriate (we can be more aggressive
    on time_cost since admin logins are much rarer than bedside PIN entries).
  - Keeping the modules separate makes auditing easier — "show me everywhere
    we hash a password" is one grep, "show me everywhere we hash a PIN" is
    another.

The API is intentionally identical to pin.py (hash_password / verify_password
/ needs_rehash / PasswordMismatch) so callers don't have to think about which
flavor they're using.
"""

from __future__ import annotations

from argon2 import PasswordHasher
from argon2 import exceptions as argon2_exceptions

# Stronger params than PINs because admin logins are infrequent and high-value.
# Memory in KiB. Time in passes. Parallelism in lanes. Hash length in bytes.
_ARGON2_MEMORY_COST = 65_536  # 64 MiB
_ARGON2_TIME_COST = 3
_ARGON2_PARALLELISM = 1
_ARGON2_HASH_LEN = 32

_hasher = PasswordHasher(
    memory_cost=_ARGON2_MEMORY_COST,
    time_cost=_ARGON2_TIME_COST,
    parallelism=_ARGON2_PARALLELISM,
    hash_len=_ARGON2_HASH_LEN,
)


class PasswordMismatch(Exception):
    """Raised when verify_password fails. Treat as generic 'login failed' —
    do NOT distinguish 'no such user' from 'bad password' in client errors.
    """


def hash_password(password: str) -> str:
    """Hash a password. Returns a self-describing PHC string."""
    if not password:
        raise ValueError("Password must not be empty")
    return _hasher.hash(password)


def verify_password(password: str, stored_hash: str) -> None:
    """Verify a password. Returns None on success, raises PasswordMismatch
    on any failure.
    """
    try:
        _hasher.verify(stored_hash, password)
    except (
        argon2_exceptions.VerifyMismatchError,
        argon2_exceptions.InvalidHashError,
        argon2_exceptions.VerificationError,
    ) as exc:
        raise PasswordMismatch from exc


def needs_rehash(stored_hash: str) -> bool:
    """Return True if the stored hash uses old parameters and should be
    rehashed on next successful login."""
    return _hasher.check_needs_rehash(stored_hash)
