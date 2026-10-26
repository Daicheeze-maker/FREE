from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import env


class Base(DeclarativeBase):
    pass


def make_engine(url: str):
    engine = create_engine(url, connect_args={"check_same_thread": False} if url.startswith("sqlite") else {})
    if url.startswith("sqlite"):
        # SQLite ignores foreign keys unless told otherwise.
        @event.listens_for(engine, "connect")
        def _fk_on(conn, _):
            conn.execute("PRAGMA foreign_keys=ON")
    return engine


engine = make_engine(env("DATABASE_URL", "sqlite:///./vesper.db"))
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
