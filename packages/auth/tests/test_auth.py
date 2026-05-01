"""Tests for the auth package — PIN hashing, JWT, permissions."""

import datetime as dt
from dataclasses import dataclass

import pytest

from nexus_care_auth import (
    InvalidTokenError,
    PINMismatch,
    can,
    hash_pin,
    issue_token,
    needs_rehash,
    verify_pin,
    verify_token,
)


# ---------------------------------------------------------------------------
# PIN
# ---------------------------------------------------------------------------
class TestPIN:
    def test_round_trip(self):
        pin = "934721"
        h = hash_pin(pin)
        verify_pin(pin, h)  # raises on failure

    def test_different_hashes_for_same_pin(self):
        """Salt randomness — same PIN must produce different hashes."""
        pin = "123456"
        assert hash_pin(pin) != hash_pin(pin)

    def test_wrong_pin_raises(self):
        h = hash_pin("123456")
        with pytest.raises(PINMismatch):
            verify_pin("654321", h)

    def test_empty_pin_rejected_at_hash(self):
        with pytest.raises(ValueError):
            hash_pin("")

    def test_garbage_hash_raises_pin_mismatch_not_some_other_error(self):
        """If the stored hash is corrupt, surface PINMismatch — never a
        crashy stack trace that could leak info to the client."""
        with pytest.raises(PINMismatch):
            verify_pin("123456", "not-a-real-hash")

    def test_phc_format(self):
        """Hash should be a self-describing PHC string starting with $argon2id$."""
        h = hash_pin("123456")
        assert h.startswith("$argon2id$"), f"Expected argon2id prefix, got: {h[:20]}"

    def test_needs_rehash_at_current_params_is_false(self):
        h = hash_pin("123456")
        assert needs_rehash(h) is False


# ---------------------------------------------------------------------------
# Tokens
# ---------------------------------------------------------------------------
SIGNING_KEY = "test-key-do-not-use-in-prod"
OTHER_KEY = "different-key"


def _issue(**overrides):
    defaults = dict(
        user_id=42,
        tenant_id=7,
        tenant_state="active",
        region="us-central",
        role="nurse",
        signing_key=SIGNING_KEY,
    )
    defaults.update(overrides)
    return issue_token(**defaults)


class TestTokens:
    def test_round_trip(self):
        issued = _issue()
        claims = verify_token(issued.token, signing_key=SIGNING_KEY)
        assert claims.sub == "42"
        assert claims.tenant_id == 7
        assert claims.tenant_state == "active"
        assert claims.region == "us-central"
        assert claims.role == "nurse"
        assert claims.exp > claims.iat
        assert len(claims.jti) == 32  # uuid4 hex

    def test_wrong_signing_key_rejected(self):
        issued = _issue()
        with pytest.raises(InvalidTokenError):
            verify_token(issued.token, signing_key=OTHER_KEY)

    def test_expired_token_rejected(self):
        # Issue a token that expired 1 second ago.
        past = dt.datetime.now(dt.UTC) - dt.timedelta(hours=9)
        issued = _issue(now=past, ttl_seconds=8 * 60 * 60)
        with pytest.raises(InvalidTokenError, match="expired"):
            verify_token(issued.token, signing_key=SIGNING_KEY)

    def test_garbage_token_rejected(self):
        with pytest.raises(InvalidTokenError):
            verify_token("nope.not.a.token", signing_key=SIGNING_KEY)

    def test_revocation_rejects_old_token(self):
        """A token issued at time T must be rejected if
        tokens_invalid_after >= T."""
        issued = _issue()
        # Revocation timestamp at or after iat → reject
        with pytest.raises(InvalidTokenError, match="revoked"):
            verify_token(
                issued.token,
                signing_key=SIGNING_KEY,
                tokens_invalid_after=issued.claims.iat,
            )

    def test_revocation_allows_newer_token(self):
        """Revocation set BEFORE the token's iat → token is fine."""
        issued = _issue()
        verify_token(
            issued.token,
            signing_key=SIGNING_KEY,
            tokens_invalid_after=issued.claims.iat - 1,
        )


# ---------------------------------------------------------------------------
# Permissions
# ---------------------------------------------------------------------------
@dataclass
class FakeUser:
    role: str


class TestPermissions:
    def test_nurse_can_administer_meds(self):
        assert can(FakeUser(role="nurse"), "administer", "med_pass") is True

    def test_caregiver_cannot_administer_meds(self):
        assert can(FakeUser(role="caregiver"), "administer", "med_pass") is False

    def test_supervisor_inherits_nurse_clinical_perms(self):
        assert can(FakeUser(role="supervisor"), "administer", "med_pass") is True
        assert can(FakeUser(role="supervisor"), "create", "soap_note") is True

    def test_supervisor_can_read_audit_log_nurse_cannot(self):
        assert can(FakeUser(role="supervisor"), "read", "audit_log") is True
        assert can(FakeUser(role="nurse"), "read", "audit_log") is False

    def test_tenant_admin_can_manage_users_supervisor_cannot(self):
        assert can(FakeUser(role="tenant_admin"), "create", "user") is True
        assert can(FakeUser(role="supervisor"), "create", "user") is False

    def test_platform_admin_cannot_read_phi(self):
        """Critical: platform admins manage tenants but must not be able to
        read clinical data through the role helper. The bright line between
        platform and clinical access is enforced here."""
        admin = FakeUser(role="platform_admin")
        assert can(admin, "read", "resident") is False
        assert can(admin, "read", "clinical_note") is False
        assert can(admin, "read", "medication") is False
        assert can(admin, "administer", "med_pass") is False
        # But they CAN do their actual job
        assert can(admin, "create", "tenant") is True
        assert can(admin, "update", "feature_flag") is True

    def test_unknown_role_denies_everything(self):
        assert can(FakeUser(role="alien"), "read", "resident") is False
        assert can(FakeUser(role=""), "read", "resident") is False
