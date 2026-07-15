"""FastAPI dependencies: DB session per request."""

from __future__ import annotations

from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy.orm import Session, sessionmaker

from buybox.persistence.db import get_engine, get_sessionmaker


@lru_cache
def _session_factory() -> sessionmaker[Session]:
    engine = get_engine()
    return get_sessionmaker(engine)


def get_db() -> Iterator[Session]:
    session = _session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
