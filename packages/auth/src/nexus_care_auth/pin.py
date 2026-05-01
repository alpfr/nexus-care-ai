"""Argon2id PIN hashing and verification.

We hash 6-digit PINs (not arbitrary passwords) because Nexus Care AI is a
bedside-tablet product where typing a strong password during med-pass is
unrealistic. To compensate for the low entropy of a 6-digit PIN, we:

  1. Hash with Argon2id at OWASP-recommended parameters (memory-hard, slow).
  2. Salt automatically per-PIN (Argon2 handles this).
  3. Rate-limit at the auth endpoint (slowapi, per-tenant).
  4. Lock accounts after 5 failed attempts for 15 minutes (handled in services).
  5. PINs are unique within a tenant, so even brute-forcing the hash gives
     the attacker only one user's PIN — they still need a valid facility code
     and the user's tenant context to do anything.

Argon2id parameters follow OWASP Password Storage Cheat Sheet (2026):

    memory_cost = 19 MiB  (m=19456 KiB)
    time_cost   = 2       (iterations)
    parallelism = 1
    hash_len    = 32 bytes

These are baked into the PasswordHasher singleton below. To upgrade
parameters in the future, increment the constants and let `needs_rehash()`
detect old hashes — they get re-hashed on next successful login.
"""

from __future__ import annotations

from argon2 import PasswordHasher
from argon2 import exceptions as argon2_exceptions

# OWASP 2026 recommended minimum for Argon2id.
# Memory in KiB. Time in passes. Parallelism in lanes. Hash length in bytes.
_ARGON2_MEMORY_COST = 19_456  # 19 MiB
_ARGON2_TIME_COST = 2
_ARGON2_PARALLELISM = 1
_ARGON2_HASH_LEN = 32

# A single hasher is fine — PasswordHasher is stateless from the caller's POV.
_hasher = PasswordHasher(
    memory_cost=_ARGON2_MEMORY_COST,
    time_cost=_ARGON2_TIME_COST,
    parallelism=_ARGON2_PARALLELISM,
    hash_len=_ARGON2_HASH_LEN,
)


class PINMismatch(Exception):
    """Raised when verify_pin fails. The caller should treat this as a generic
    'login failed' — do NOT distinguish 'no such user' from 'bad PIN' in
    error messages returned to the client. That distinction leaks user
    enumeration to attackers.
    """


def hash_pin(pin: str) -> str:
    """Hash a PIN. Returns a self-describing PHC string, e.g.
    `$argon2id$v=19$m=19456,t=2,p=1$<salt>$<hash>`.

    The PHC string contains the algorithm, version, parameters, salt, and
    hash — everything verify_pin() needs. Store this string as-is; do not
    split it.
    """
    if not pin:
        raise ValueError("PIN must not be empty")
    return _hasher.hash(pin)


def verify_pin(pin: str, stored_hash: str) -> None:
    """Verify a PIN against a stored hash. Returns None on success, raises
    PINMismatch on failure.

    Constant-time comparison is built into the hasher. Do not catch this
    exception and continue — the caller should treat it as 'login failed',
    record the failed attempt for lockout tracking, and return a generic
    error to the client.
    """
    try:
        _hasher.verify(stored_hash, pin)
    except (
        argon2_exceptions.VerifyMismatchError,
        argon2_exceptions.InvalidHashError,
        argon2_exceptions.VerificationError,
    ) as exc:
        raise PINMismatch from exc


def needs_rehash(stored_hash: str) -> bool:
    """Return True if the stored hash uses old parameters and should be
    rehashed on next successful login.

    Standard rotation pattern: after verify_pin() succeeds, check
    needs_rehash(); if True, recompute hash_pin(pin) and update the user
    record. This lets us tighten Argon2 parameters as hardware improves
    without forcing password resets.
    """
    return _hasher.check_needs_rehash(stored_hash)
