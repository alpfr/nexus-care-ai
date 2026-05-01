"""Declarative Base and shared mixins.

Two Postgres schemas are defined here as constants so models reference them
consistently. Alembic uses these names when generating migrations.
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import DateTime, MetaData, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

PLATFORM_SCHEMA = "platform"
TENANT_DATA_SCHEMA = "tenant_data"


# Naming convention so Alembic auto-generates predictable, stable
# constraint names (no auto-named indexes that change on every diff).
_NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Common Declarative Base for every model in the project."""

    metadata = MetaData(naming_convention=_NAMING_CONVENTION)


class TimestampMixin:
    """`created_at` and `updated_at` columns. Server-side defaults so DB is
    always the truth even if the application forgets to set them."""

    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
