from flask_login import LoginManager
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import CSRFProtect
import sqlite3

from sqlalchemy import MetaData, event
from sqlalchemy.engine import Engine

# Named constraints keep Alembic migrations deterministic on SQLite.
naming_convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

db = SQLAlchemy(metadata=MetaData(naming_convention=naming_convention))
migrate = Migrate(render_as_batch=True)
login_manager = LoginManager()
csrf = CSRFProtect()



@event.listens_for(Engine, "connect")
def _sqlite_pragmas(dbapi_connection, _record):
    """SQLite settings for every connection: enforce foreign keys (relational integrity), wait instead of failing when
    another request is writing, and use WAL so readers never block the writer (Waitress serves 8 requests at once)."""
    if not isinstance(dbapi_connection, sqlite3.Connection):
        return
    cur = dbapi_connection.cursor()
    cur.execute("PRAGMA foreign_keys=ON")
    cur.execute("PRAGMA busy_timeout=5000")
    try:
        if cur.execute("PRAGMA database_list").fetchone()[2]:  # a file database (not :memory:)
            cur.execute("PRAGMA journal_mode=WAL")
            cur.execute("PRAGMA synchronous=NORMAL")
    except sqlite3.DatabaseError:
        pass
    cur.close()
