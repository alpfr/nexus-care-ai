"""Clinical route handlers — residents, medications, medication orders.

Every endpoint in this package:
  - requires require_user (sets tenant context)
  - filters all queries by current_tenant_id() — no exceptions
  - calls assert_can_write_phi() before any PHI write (the gate)
  - records audit log entries for reads and writes
  - uses can() from nexus_care_auth for action-level permission checks
"""
