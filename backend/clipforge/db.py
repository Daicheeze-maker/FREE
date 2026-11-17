"""SQLite engine/session handling."""
from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import paths


class Base(DeclarativeBase):
    pass


_engine = None
_Session: sessionmaker[Session] | None = None


def init_db() -> None:
    """(Re)create the engine for the current data directory and create tables."""
    global _engine, _Session
    paths.ensure()
    if _engine is not None:
        _engine.dispose()
    _engine = create_engine(
        f"sqlite:///{paths.db.as_posix()}",
        connect_args={"check_same_thread": False, "timeout": 30},
    )

    @event.listens_for(_engine, "connect")
    def _pragmas(dbapi_conn, _):  # WAL keeps the UI readable while a job writes
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA foreign_keys=ON")
        cur.execute("PRAGMA synchronous=NORMAL")
        cur.close()

    _Session = sessionmaker(_engine, expire_on_commit=False)
    from . import models  # noqa: F401  (register tables)

    Base.metadata.create_all(_engine)


@contextmanager
def session() -> Iterator[Session]:
    if _Session is None:
        init_db()
    s = _Session()  # type: ignore[misc]
    try:
        yield s
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()
