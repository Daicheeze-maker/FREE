"""`python -m flask --app wsgi doctor`: checks that this machine (or VM) can run the store cleanly.

Looks at Python, the installed packages, the .env file, the database (schema version, integrity, foreign keys), the folders
the store writes to, and then opens the main pages and API endpoints in-process. Prints one line per check and exits with
code 1 if anything failed, so scripts (vm-check.sh) and people can both read it.
"""
import importlib
import os
import socket
import sys
from pathlib import Path

from flask import current_app
from sqlalchemy import inspect, text

from .config import BASE_DIR
from .extensions import db

PACKAGES = ["flask", "werkzeug", "jinja2", "flask_sqlalchemy", "sqlalchemy", "flask_migrate", "alembic", "flask_login",
            "flask_wtf", "wtforms", "email_validator", "requests", "dotenv", "PIL", "phonenumbers", "waitress"]


class Report:
    def __init__(self, echo):
        self.echo, self.failed, self.warned = echo, 0, 0

    def ok(self, label, detail=""):
        self.echo(f"  [ OK ] {label}" + (f"  ({detail})" if detail else ""))

    def warn(self, label, detail=""):
        self.warned += 1
        self.echo(f"  [WARN] {label}" + (f"  ({detail})" if detail else ""))

    def fail(self, label, detail=""):
        self.failed += 1
        self.echo(f"  [FAIL] {label}" + (f"  ({detail})" if detail else ""))


def run(echo=print):
    r = Report(echo)
    cfg = current_app.config

    echo("Environment")
    if sys.version_info >= (3, 11):
        r.ok("Python version", sys.version.split()[0])
    else:
        r.fail("Python version", f"{sys.version.split()[0]}: needs 3.11 or newer")
    in_venv = sys.prefix != getattr(sys, "base_prefix", sys.prefix)
    (r.ok if in_venv else r.warn)("Isolated virtual environment (.venv)", sys.prefix if in_venv else "not using .venv")
    missing = []
    for name in PACKAGES:
        try:
            importlib.import_module(name)
        except ImportError:
            missing.append(name)
    if missing:
        r.fail("Required packages", "missing: " + ", ".join(missing) + " -> python -m pip install -r requirements.txt")
    else:
        r.ok("Required packages", f"{len(PACKAGES)} installed")
    env_file = BASE_DIR / ".env"
    if env_file.is_file():
        r.ok(".env file", str(env_file))
    else:
        r.warn(".env file", "missing: run scripts/setup.sh (or setup.bat) to create it")
    key = os.environ.get("SECRET_KEY", "")
    if key and not key.startswith("change-me") and len(key) >= 32:
        r.ok("SECRET_KEY", "set")
    else:
        r.warn("SECRET_KEY", "not set in .env: sign-ins reset every restart")

    echo("Database")
    try:
        db.session.execute(text("SELECT 1"))
        r.ok("Connects", cfg["SQLALCHEMY_DATABASE_URI"].split("///")[-1])
    except Exception as exc:
        r.fail("Connects", f"{type(exc).__name__}: {exc}")
        return _finish(r, echo)
    try:
        from alembic.runtime.migration import MigrationContext
        from alembic.script import ScriptDirectory
        from flask_migrate import Migrate  # noqa: F401
        script = ScriptDirectory.from_config(current_app.extensions["migrate"].migrate.get_config(
            current_app.extensions["migrate"].directory))
        with db.engine.connect() as conn:
            current = MigrationContext.configure(conn).get_current_revision()
        head = script.get_current_head()
        (r.ok if current == head else r.fail)("Schema is up to date", f"{current} / latest {head}"
                                               if current == head else f"at {current}, latest is {head}: run init-db")
    except Exception as exc:
        r.warn("Schema version", f"couldn't check ({type(exc).__name__})")
    tables = inspect(db.engine).get_table_names()
    if not {"user", "product", "category"} <= set(tables):
        r.fail("Store tables exist", "the database is empty: run python -m flask --app wsgi init-db, then seed")
        return _finish(r, echo)
    if db.engine.dialect.name == "sqlite":
        integrity = db.session.execute(text("PRAGMA integrity_check")).scalar()
        (r.ok if integrity == "ok" else r.fail)("File integrity", integrity)
        fk_on = db.session.execute(text("PRAGMA foreign_keys")).scalar()
        (r.ok if fk_on else r.fail)("Foreign keys enforced", "on" if fk_on else "off")
        broken = db.session.execute(text("PRAGMA foreign_key_check")).fetchall()
        (r.ok if not broken else r.warn)("No broken links between tables", f"{len(broken)} broken row(s)" if broken else "")
        mode = db.session.execute(text("PRAGMA journal_mode")).scalar()
        (r.ok if mode in ("wal", "memory") else r.warn)("Journal mode", mode)
    counts = {t: db.session.execute(text(f'SELECT COUNT(*) FROM "{t}"')).scalar() for t in ("product", "category", "user")
              if t in tables}
    if counts.get("product"):
        r.ok("Catalog loaded", ", ".join(f"{v} {k}s" if k != "category" else f"{v} categories" for k, v in counts.items()))
    else:
        r.fail("Catalog loaded", "no products: run python -m flask --app wsgi seed")
    from .models import User
    (r.ok if User.query.filter_by(role="admin").first() else r.warn)(
        "Admin account", "exists" if User.query.filter_by(role="admin").first()
        else "none yet: Sign in page -> Set up the admin account")

    echo("Folders")
    for label, path in (("Database folder", Path(cfg["SQLALCHEMY_DATABASE_URI"].split("///")[-1]).parent),
                        ("Uploads folder", Path(cfg["UPLOAD_FOLDER"]))):
        try:
            path.mkdir(parents=True, exist_ok=True)
            probe = path / ".write-test"
            probe.write_text("ok")
            probe.unlink()
            r.ok(f"{label} is writable", str(path))
        except OSError as exc:
            r.fail(f"{label} is writable", f"{path}: {exc}")

    echo("Pages and API (opened inside the app)")
    from .models import Category, Product
    client = current_app.test_client()
    product = Product.query.filter_by(status="active").order_by(Product.id).first()
    category = Category.query.order_by(Category.position).first()
    urls = ["/", "/shop/", "/account/login", "/account/register", "/healthz", "/api/docs", "/api/v1", "/api/v1/health",
            "/api/v1/products", "/api/v1/categories"]
    if category:
        urls.append(f"/shop/c/{category.slug}")
    if product:
        urls += [f"/shop/p/{product.slug}", f"/api/v1/products/{product.slug}"]
    bad = []
    for url in urls:
        try:
            code = client.get(url).status_code
        except Exception as exc:  # report, keep checking
            code = f"crash: {type(exc).__name__}"
        if code != 200:
            bad.append(f"{url} -> {code}")
    if bad:
        r.fail(f"{len(urls) - len(bad)} of {len(urls)} pages answer", "; ".join(bad))
    else:
        r.ok(f"All {len(urls)} pages and API endpoints answer 200")

    echo("Network")
    host, port = os.environ.get("HOST", "127.0.0.1"), int(os.environ.get("PORT", "5000"))
    r.ok("Server address", f"{host}:{port}" + ("  (reachable through VM port forwarding)" if host == "0.0.0.0"
                                               else "  (this machine only; use HOST=0.0.0.0 for VM port forwarding)"))
    if port_in_use(port):
        r.ok(f"Port {port}", "in use: the store (or another program) is running on it")
    else:
        r.ok(f"Port {port}", "free: the store can start on it")
    return _finish(r, echo)


def _finish(r, echo):
    echo("")
    if r.failed:
        echo(f"RESULT: {r.failed} problem(s) found" + (f", {r.warned} warning(s)" if r.warned else "") + ".")
    else:
        echo("RESULT: all checks passed" + (f" ({r.warned} warning(s))" if r.warned else "") + ".")
    return r.failed == 0


def port_in_use(port, host="127.0.0.1"):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex((host, port)) == 0
