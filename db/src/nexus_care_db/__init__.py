"""Nexus Care DB — shared schema for all services.

The Base class, schema namespaces, and all SQLAlchemy models live here.
Both services/api and services/platform import their models from this
package so there is exactly one source of truth.
"""

from nexus_care_db.base import PLATFORM_SCHEMA, TENANT_DATA_SCHEMA, Base
from nexus_care_db.clinical.medication_orders import MedicationOrder
from nexus_care_db.clinical.medications import Medication
from nexus_care_db.clinical.residents import Resident

# Platform schema models (SaaS plumbing).
from nexus_care_db.platform.feature_flags import FeatureFlag
from nexus_care_db.platform.platform_admins import PlatformAdmin
from nexus_care_db.platform.tenants import Tenant
from nexus_care_db.platform.users import User

# Tenant-data schema models (PHI-bearing).
from nexus_care_db.tenant_data.audit_log import AuditLog

__all__ = [
    "PLATFORM_SCHEMA",
    "TENANT_DATA_SCHEMA",
    "AuditLog",
    "Base",
    "FeatureFlag",
    "Medication",
    "MedicationOrder",
    "PlatformAdmin",
    "Resident",
    "Tenant",
    "User",
]
