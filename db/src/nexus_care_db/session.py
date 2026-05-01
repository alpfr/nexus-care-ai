"""Engine and Session factory.

A single sync engine per process. Engines are expensive to create; the
SessionLocal factory wraps it so route handlers get fresh, short-lived
Sessions per request.

We use sync SQLAlchemy (not async) for now because:
  - Postgres connection pooling is well-understood synchronously.
  - FastAPI's Depends() pattern handles sync sessions cleanly.
  - Async ORM is faster only when you have many concurrent connections
    starving on I/O — not our profile yet.

We can move to async later without changing the model definitions.
"""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker


def make_engine(database_url: str, *, echo: bool = False) -> Engine:
    """Create a SQLAlchemy engine. `database_url` is a Postgres DSN, e.g.

        postgresql+psycopg://user:pass@host:5433/nexus_care
    """
    return create_engine(
        database_url,
        echo=echo,
        future=True,
        pool_pre_ping=True,  # detect broken connections cheaply
        pool_recycle=3600,  # cycle connections every hour
    )


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(
        bind=engine,
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
        class_=Session,
    )


@contextmanager
def session_scope(factory: sessionmaker[Session]) -> Generator[Session, None, None]:
    """Provide a transactional scope around a series of operations.

    Used in scripts and tests. FastAPI handlers use the FastAPI dep system
    instead — see services/api/src/nexus_care_api/deps.py.
    """
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
