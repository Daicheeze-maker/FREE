"""One-time "Set up the admin" page: no terminal needed, only on this computer, only while the store has no admin."""
from velora import create_app
from velora.cli import init_database
from velora.extensions import db
from velora.models import AuditLog, User
from velora.seed import seed

from .conftest import IsolatedClient

FORM = {"full_name": "Store Owner", "email": "Owner@Example.com", "password": "Owner-Pass-7", "confirm": "Owner-Pass-7"}


def _app(tmp_path):
    app = create_app("testing", SQLALCHEMY_DATABASE_URI=f"sqlite:///{tmp_path / 's.db'}")
    app.test_client_class = IsolatedClient
    with app.app_context():
        init_database()
        seed()
    return app


def test_sign_in_page_offers_the_set_up_while_there_is_no_admin(tmp_path):
    app = _app(tmp_path)
    page = app.test_client().get("/account/login").get_data(as_text=True)
    assert "Set up the admin account" in page and "/account/setup-admin" in page
    assert app.test_client().get("/account/setup-admin").status_code == 200


def test_set_up_creates_the_admin_signs_in_and_then_the_page_is_gone(tmp_path):
    app = _app(tmp_path)
    c = app.test_client()
    r = c.post("/account/setup-admin", data=FORM)
    assert r.status_code == 302 and r.headers["Location"].endswith("/admin/")
    assert c.get("/admin/").status_code == 200  # signed in as the admin straight away
    with app.app_context():
        u = User.query.filter_by(email="owner@example.com").one()
        assert u.role == "admin" and u.check_password("Owner-Pass-7")
        assert AuditLog.query.filter_by(action="admin.setup").count() == 1
    other = app.test_client()
    assert other.get("/account/setup-admin").status_code == 404  # never a second time
    assert other.post("/account/setup-admin", data={**FORM, "email": "x@example.com"}).status_code == 404
    assert "Set up the admin account" not in other.get("/account/login").get_data(as_text=True)
    r = other.post("/account/login", data={"email": "owner@example.com", "password": "Owner-Pass-7"})
    assert r.headers["Location"].endswith("/admin/")


def test_only_works_on_this_computer(tmp_path):
    app = _app(tmp_path)
    away = app.test_client()
    assert away.get("/account/setup-admin", environ_base={"REMOTE_ADDR": "192.168.1.20"}).status_code == 404
    assert away.get("/account/setup-admin", headers={"X-Forwarded-For": "203.0.113.9"}).status_code == 404
    page = away.get("/account/login", environ_base={"REMOTE_ADDR": "192.168.1.20"}).get_data(as_text=True)
    assert "Set up the admin account" not in page


def test_validation_and_csrf_style_checks(tmp_path):
    app = _app(tmp_path)
    c = app.test_client()
    r = c.post("/account/setup-admin", data={**FORM, "confirm": "nope"})
    assert r.status_code == 200 and "field__error" in r.get_data(as_text=True)
    r = c.post("/account/setup-admin", data={**FORM, "password": "short", "confirm": "short"})
    assert r.status_code == 200
    with app.app_context():
        assert User.query.filter_by(role="admin").count() == 0


def test_a_shop_account_with_that_email_becomes_the_admin(tmp_path):
    app = _app(tmp_path)
    app.test_client().post("/account/register", data={"full_name": "Aries", "email": "owner@example.com",
                                                      "password": "Other123", "confirm": "Other123", "accept": "y"})
    r = app.test_client().post("/account/setup-admin", data=FORM)
    assert r.headers["Location"].endswith("/admin/")
    with app.app_context():
        u = User.query.filter_by(email="owner@example.com").one()
        assert u.role == "admin" and u.check_password("Owner-Pass-7") and User.query.filter_by(email="owner@example.com").count() == 1


def test_stores_that_already_have_an_admin_never_show_it(client):
    assert client.get("/account/setup-admin").status_code == 404  # the test store has an admin


def test_create_admin_bat_always_stays_open_to_show_what_happened(app):
    bat = open("create-admin.bat", newline="").read()
    assert "\r\n" in bat and bat.count("pause") >= 2 and "Set up the admin account" in bat
