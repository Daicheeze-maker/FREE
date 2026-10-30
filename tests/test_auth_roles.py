from velora.extensions import db
from velora.models import AuditLog, User

from .conftest import get_user, login


def test_register_creates_customer_and_ignores_role_injection(client):
    r = client.post("/account/register", data={
        "full_name": "New Person", "email": "new@example.com", "password": "Secret123",
        "confirm": "Secret123", "accept": "y", "role": "admin",
    })
    assert r.status_code == 302
    u = get_user("new@example.com")
    assert u.role == "customer"
    assert u.password_hash != "Secret123" and u.check_password("Secret123")


def test_register_validation_errors(client):
    r = client.post("/account/register", data={"full_name": "X", "email": "bad", "password": "short", "confirm": "nope"})
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert "field__error" in html
    assert get_user("bad") is None


def test_duplicate_email_rejected(client):
    r = client.post("/account/register", data={"full_name": "Dup", "email": "customer@velora.example",
                                               "password": "Secret123", "confirm": "Secret123", "accept": "y"})
    assert "already exists" in r.get_data(as_text=True)


def test_login_success_and_wrong_password(client):
    assert login(client, "customer@velora.example", "nope").status_code == 200
    r = login(client, "customer@velora.example", "Customer123!")
    assert r.status_code == 302 and r.headers["Location"].endswith("/account/")


def test_lockout_after_repeated_failures(client, app):
    for _ in range(app.config["LOGIN_MAX_ATTEMPTS"]):
        login(client, "customer@velora.example", "wrong")
    r = login(client, "customer@velora.example", "Customer123!")
    assert r.status_code == 200 and "Too many failed attempts" in r.get_data(as_text=True)
    assert AuditLog.query.filter_by(action="auth.lockout").count() == 1


def test_disabled_account_cannot_sign_in(client):
    u = get_user("jonah@example.com")
    u.is_active_account = False
    db.session.commit()
    assert login(client, "jonah@example.com", "Customer123!").status_code == 403


def test_logout_requires_post(customer):
    assert customer.get("/account/logout").status_code == 405
    assert customer.post("/account/logout").status_code == 302
    assert customer.get("/account/").status_code == 302  # back to login


def test_guest_redirected_from_protected_pages(client):
    for url in ("/account/", "/account/orders", "/checkout", "/seller/", "/admin/"):
        r = client.get(url)
        assert r.status_code == 302 and "/account/login" in r.headers["Location"], url


def test_customer_cannot_access_staff_areas(customer):
    for url in ("/seller/", "/seller/products", "/admin/", "/admin/users", "/admin/audit"):
        assert customer.get(url).status_code == 403, url


def test_seller_cannot_access_admin(seller):
    assert seller.get("/seller/").status_code == 200
    assert seller.get("/admin/").status_code == 403
    assert seller.post("/admin/users/1", data={"role": "admin", "is_active_account": "y"}).status_code == 403


def test_four_distinct_dashboards(client):
    assert "Featured this week" in client.get("/").get_data(as_text=True)  # guest storefront
    login(client, "customer@velora.example", "Customer123!")
    assert "Customer account" in client.get("/account/").get_data(as_text=True)
    client.post("/account/logout")
    login(client, "seller@velora.example", "Seller123!")
    html = client.get("/seller/").get_data(as_text=True)
    assert "Store dashboard" in html and "Fulfilment queue" in html
    client.post("/account/logout")
    login(client, "admin@velora.example", "Admin123!")
    html = client.get("/admin/").get_data(as_text=True)
    assert "Store-wide overview" in html and "Integrations" in html


def test_admin_changes_role_with_audit(admin):
    u = get_user("bea@example.com")
    r = admin.post(f"/admin/users/{u.id}", data={"role": "seller", "is_active_account": "y"})
    assert r.status_code == 302
    db.session.refresh(u)
    assert u.role == "seller"
    assert AuditLog.query.filter_by(action="user.role_change").count() == 1


def test_admin_cannot_demote_self(admin):
    me = get_user("admin@velora.example")
    admin.post(f"/admin/users/{me.id}", data={"role": "customer", "is_active_account": "y"})
    db.session.refresh(me)
    assert me.role == "admin"


def test_disabling_user_logs_them_out(app):
    c = app.test_client()
    login(c, "paolo@example.com", "Customer123!")
    assert c.get("/account/").status_code == 200
    u = get_user("paolo@example.com")
    u.is_active_account = False
    db.session.commit()
    assert c.get("/account/").status_code == 302


def test_open_redirect_blocked(client):
    r = client.post("/account/login?next=https://evil.example/x", data={"email": "customer@velora.example", "password": "Customer123!"})
    assert "evil.example" not in r.headers["Location"]


def test_csrf_enforced_when_enabled(app):
    app.config["WTF_CSRF_ENABLED"] = True
    c = app.test_client()
    r = c.post("/account/login", data={"email": "customer@velora.example", "password": "Customer123!"})
    assert r.status_code == 400


def test_health_check(client):
    r = client.get("/healthz")
    assert r.status_code == 200 and r.json["status"] == "ok"


def test_security_headers(client):
    r = client.get("/")
    assert r.headers["X-Frame-Options"] == "DENY"
    assert "script-src 'self'" in r.headers["Content-Security-Policy"]
