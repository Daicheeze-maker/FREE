"""start.bat makes sure the store's admin account exists (login from the local .env, never from the repository)."""
from velora import create_app
from velora.cli import init_database
from velora.extensions import db
from velora.models import User
from velora.seed import seed

from .conftest import IsolatedClient

PW = "Test-Admin-9"  # test value only
ARGS = ["ensure-admin", "--email", "owner@example.com", "--password", PW, "--name", "Store Admin"]


def _app(tmp_path):
    app = create_app("testing", SQLALCHEMY_DATABASE_URI=f"sqlite:///{tmp_path / 'a.db'}")
    app.test_client_class = IsolatedClient
    with app.app_context():
        init_database()
        seed()
    return app


def test_start_up_creates_the_admin_and_it_signs_in_to_the_admin_console(tmp_path):
    app = _app(tmp_path)
    out = app.test_cli_runner().invoke(args=ARGS).output
    assert "Admin account ready: owner@example.com" in out
    c = app.test_client()
    r = c.post("/account/login", data={"email": "owner@example.com", "password": PW})
    assert r.status_code == 302 and r.headers["Location"].endswith("/admin/")
    assert c.get("/admin/").status_code == 200 and c.get("/admin/sellers").status_code == 200
    bad = app.test_client().post("/account/login", data={"email": "owner@example.com", "password": "nope"})
    assert bad.status_code == 200  # the real password is still required


def test_running_it_again_changes_nothing_and_keeps_a_changed_password(tmp_path):
    app = _app(tmp_path)
    runner = app.test_cli_runner()
    runner.invoke(args=ARGS)
    with app.app_context():
        u = User.query.filter_by(email="owner@example.com").one()
        u.set_password("MyNewPass1")  # the owner changed it in the store
        db.session.commit()
    assert runner.invoke(args=ARGS).output.strip() == ""
    with app.app_context():
        u = User.query.filter_by(email="owner@example.com").one()
        assert User.query.filter_by(email="owner@example.com").count() == 1 and u.check_password("MyNewPass1")


def test_a_shop_account_with_that_email_becomes_the_admin(tmp_path):
    app = _app(tmp_path)
    c = app.test_client()
    c.post("/account/register", data={"full_name": "Aries", "email": "owner@example.com", "password": "Other123",
                                      "confirm": "Other123", "accept": "y"})
    out = app.test_cli_runner().invoke(args=ARGS).output
    assert "owner@example.com is now an admin account" in out
    with app.app_context():
        u = User.query.filter_by(email="owner@example.com").one()
        assert u.role == "admin" and u.check_password(PW)
    r = app.test_client().post("/account/login", data={"email": "owner@example.com", "password": PW})
    assert r.headers["Location"].endswith("/admin/")


def test_start_up_cleanup_never_removes_the_owners_admin(tmp_path):
    app = _app(tmp_path)
    runner = app.test_cli_runner()
    runner.invoke(args=ARGS)
    runner.invoke(args=["upgrade-demo"])
    with app.app_context():
        assert User.query.filter_by(email="owner@example.com", role="admin").count() == 1


def test_admin_login_can_come_from_the_local_env_file(tmp_path, monkeypatch):
    app = _app(tmp_path)
    assert app.test_cli_runner().invoke(args=["ensure-admin"]).output.strip() == ""  # not configured: does nothing
    monkeypatch.setenv("ADMIN_EMAIL", "Owner@Example.com")
    monkeypatch.setenv("ADMIN_PASSWORD", PW)
    assert "Admin account ready: owner@example.com" in app.test_cli_runner().invoke(args=["ensure-admin"]).output
    r = app.test_client().post("/account/login", data={"email": "owner@example.com", "password": PW})
    assert r.headers["Location"].endswith("/admin/")


def test_no_admin_password_is_kept_in_the_repository(app):
    for f in ("start.bat", "start.sh", ".env.example"):
        text = open(f, newline="").read()
        assert "ensure-admin" in text or "ADMIN_PASSWORD=" in text
        assert "--password" not in text, f  # no password is written into the scripts
