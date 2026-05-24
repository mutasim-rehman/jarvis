"""Database session factory."""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.app.config import settings

_engine = None
_SessionLocal = None


def _ensure_engine():
    global _engine, _SessionLocal
    if _engine is not None:
        return
    url = settings.resolved_database_url()
    if not url:
        return
    _engine = create_engine(url, pool_pre_ping=True)
    _SessionLocal = sessionmaker(bind=_engine, autocommit=False, autoflush=False)


def database_configured() -> bool:
    return bool(settings.resolved_database_url())


@contextmanager
def session_scope() -> Generator[Session, None, None]:
    _ensure_engine()
    if _SessionLocal is None:
        raise RuntimeError("DATABASE_URL is not configured")
    session = _SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_db() -> Generator[Session, None, None]:
    _ensure_engine()
    if _SessionLocal is None:
        raise RuntimeError("DATABASE_URL is not configured")
    session = _SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_db_optional() -> Generator[Session | None, None, None]:
    if not database_configured():
        yield None
        return
    yield from get_db()
