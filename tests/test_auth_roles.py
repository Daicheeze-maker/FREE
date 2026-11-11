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
    r = client.post("/account/register", data={"full_name": "Dup", "email": "buyer1@velora.example",
                                               "password": "Secret123", "confirm": "Secret123", "accept": "y"})
    assert "already exists" in r.get_data(as_text=True)


def test_login_success_and_wrong_password(client):
    assert login(client, "admin@velora.example", "nope").status_code == 200  # staff need the real password
    r = login(client, "admin@velora.example", "Admin123!")
    assert r.status_code == 302 and r.headers["Location"].endswith("/admin/")


def test_buyer_signs_in_with_any_password(client):
    assert login(client, "repeat@example.com", "first").status_code == 302
    client.post("/account/logout")
    assert login(client, "repeat@example.com", "different").status_code == 302
    assert client.get("/account/").status_code == 200


def test_login_creates_linked_buyer_and_seller_profiles(client):
    login(client, "both@example.com", "x")
    buyer = get_user("both@example.com")
    seller = get_user("both@example.com#seller")
    assert buyer.role == "customer" and seller.role == "seller"
    assert buyer.linked_profile.id == seller.id and seller.linked_profile.id == buyer.id
    assert "Switch to seller profile" in client.get("/account/").get_data(as_text=True)

    r = client.post("/account/switch-profile")
    assert r.status_code == 302 and r.headers["Location"].endswith("/seller/")
    assert client.get("/seller/").status_code == 200
    assert "Switch to buyer profile" in client.get("/seller/").get_data(as_text=True)

    r = client.post("/account/switch-profile")
    assert r.headers["Location"].endswith("/account/")
    assert client.get("/account/").status_code == 200


def test_repeat_login_does_not_duplicate_profiles(client):
    login(client, "once@example.com", "x")
    client.post("/account/logout")
    n = User.query.count()
    login(client, "once@example.com", "x")
    assert User.query.count() == n


def test_typing_seller_suffix_signs_in_as_buyer(client):
    login(client, "suffix@example.com#seller", "x")
    assert get_user("suffix@example.com").role == "customer"
    assert client.get("/account/").status_code == 200


def test_admin_has_no_other_profile_to_switch_to(admin):
    assert admin.post("/account/switch-profile").status_code == 404


def test_two_buyers_and_two_sellers_are_seeded(app):
    from velora.models import User
    buyers = User.query.filter_by(role="customer").all()
    sellers = User.query.filter_by(role="seller").all()
    assert sorted(b.email for b in buyers) == ["buyer1@velora.example", "buyer2@velora.example"]
    assert len(sellers) == 2 and all(s.linked_profile in buyers for s in sellers)
    assert all(b.linked_profile is not None for b in buyers)
    assert {b.balance_minor for b in buyers} == {50_000_000}  # PHP 500,000.00 each


def test_seller_profile_can_switch_back_to_buyer(seller):
    assert "Store dashboard" in seller.get("/seller/").get_data(as_text=True)
    assert seller.post("/account/switch-profile").status_code == 302
    assert seller.get("/seller/").status_code == 403  # back on the buyer profile


def test_unknown_login_creates_customer(client):
    r = login(client, "someone.random@example.com", "x")
    assert r.status_code == 302 and "/account" in r.headers["Location"]
    u = get_user("someone.random@example.com")
    assert u.role == "customer" and u.full_name == "Someone Random"
    assert client.get("/account/").status_code == 200


def test_login_accepts_text_that_is_not_an_email(client):
    assert login(client, "asdf", "x").status_code == 302
    assert get_user("asdf").role == "customer"


def test_auto_login_never_opens_staff_accounts(client):
    assert login(client, "admin@velora.example", "guess").status_code == 200
    assert client.get("/admin/").status_code in (302, 403)


def test_lockout_after_repeated_failures(client, app):
    for _ in range(app.config["LOGIN_MAX_ATTEMPTS"]):
        login(client, "admin@velora.example", "wrong")
    r = login(client, "admin@velora.example", "Admin123!")
    assert r.status_code == 200 and "Too many failed attempts" in r.get_data(as_text=True)
    assert AuditLog.query.filter_by(action="auth.lockout").count() == 1


def test_disabled_account_cannot_sign_in(client):
    u = get_user("buyer2@velora.example")
    u.is_active_account = False
    db.session.commit()
    assert login(client, "buyer2@velora.example", "Buyer123!").status_code == 403


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
    login(client, "buyer1@velora.example", "Buyer123!")
    assert "Customer account" in client.get("/account/").get_data(as_text=True)
    client.post("/account/switch-profile")  # the same person's seller profile
    html = client.get("/seller/").get_data(as_text=True)
    assert "Store dashboard" in html and "Fulfilment queue" in html
    client.post("/account/logout")
    login(client, "admin@velora.example", "Admin123!")
    html = client.get("/admin/").get_data(as_text=True)
    assert "Store-wide overview" in html and "Integrations" in html


def test_admin_changes_role_with_audit(admin):
    u = get_user("buyer2@velora.example")
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
    login(c, "buyer2@velora.example", "Buyer123!")
    assert c.get("/account/").status_code == 200
    u = get_user("buyer2@velora.example")
    u.is_active_account = False
    db.session.commit()
    assert c.get("/account/").status_code == 302


def test_open_redirect_blocked(client):
    r = client.post("/account/login?next=https://evil.example/x", data={"email": "buyer1@velora.example", "password": "Buyer123!"})
    assert "evil.example" not in r.headers["Location"]


def test_csrf_enforced_when_enabled(app):
    app.config["WTF_CSRF_ENABLED"] = True
    c = app.test_client()
    r = c.post("/account/login", data={"email": "buyer1@velora.example", "password": "Buyer123!"})
    assert r.status_code == 400


def test_health_check(client):
    r = client.get("/healthz")
    assert r.status_code == 200 and r.json["status"] == "ok"


def test_security_headers(client):
    r = client.get("/")
    assert r.headers["X-Frame-Options"] == "DENY"
    assert "script-src 'self'" in r.headers["Content-Security-Policy"]
