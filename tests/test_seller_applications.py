"""Selling works like a marketplace: buyers apply, only an admin can approve, approval creates the seller profile."""
from velora.extensions import db
from velora.models import AuditLog, Notification, SellerApplication, User

from .conftest import get_user, login

APPLY = {"shop_name": "Manila Time House", "phone": "+63 917 555 0142",
         "about": "Pre-owned automatic watches, serviced and tested before sale.", "agree": "y"}


def register(client, email, kind=None):
    data = {"full_name": "Sam Shop", "email": email, "password": "Secret123", "confirm": "Secret123", "accept": "y"}
    if kind:
        data["account_type"] = kind
    return client.post("/account/register", data=data)


def _apply(app, email="sam@example.com"):
    c = app.test_client()
    register(c, email, "seller")
    c.post("/account/sell", data=APPLY)
    return c, SellerApplication.query.join(User, SellerApplication.user_id == User.id).filter(User.email == email).one()


def test_buyer_applies_and_waits(app):
    c, a = _apply(app)
    assert a.status == "pending" and a.shop_name == "Manila Time House"
    page = c.get("/account/sell").get_data(as_text=True)
    assert "Waiting for the admin" in page and "Send application" not in page
    assert get_user("sam@example.com#seller") is None and c.get("/seller/").status_code == 403
    c.post("/account/sell", data=APPLY)  # can't send a second one while waiting
    assert SellerApplication.query.count() == 1
    admins = User.query.filter_by(role="admin").all()
    assert all(Notification.query.filter_by(user_id=u.id, title="New seller application").count() == 1 for u in admins)


def test_application_is_validated(app):
    c = app.test_client()
    register(c, "v@example.com", "seller")
    r = c.post("/account/sell", data={**APPLY, "about": "short", "agree": ""})
    assert r.status_code == 200 and "field__error" in r.get_data(as_text=True)
    assert SellerApplication.query.count() == 0


def test_only_the_admin_can_decide(app, customer, seller):
    _, a = _apply(app)
    for c in (customer, seller):
        assert c.get("/admin/seller-requests").status_code in (302, 403)
        assert c.post(f"/admin/seller-requests/{a.id}/approve").status_code in (302, 403)
    db.session.expire_all()
    assert db.session.get(SellerApplication, a.id).status == "pending"


def test_admin_approves_and_the_buyer_becomes_a_seller(app, admin):
    c, a = _apply(app)
    page = admin.get("/admin/seller-requests").get_data(as_text=True)
    assert "Manila Time House" in page and "Pre-owned automatic watches" in page
    assert '<span class="count-pill">1</span>' in admin.get("/admin/").get_data(as_text=True)  # sidebar badge
    r = admin.post(f"/admin/seller-requests/{a.id}/approve")
    assert r.status_code == 302
    db.session.expire_all()
    s = get_user("sam@example.com#seller")
    assert s and s.role == "seller" and s.is_active_account and s.full_name == "Manila Time House"
    assert db.session.get(SellerApplication, a.id).status == "approved"
    assert AuditLog.query.filter_by(action="seller.approve").count() == 1
    buyer = get_user("sam@example.com")
    assert Notification.query.filter_by(user_id=buyer.id, title="You're now a seller!").count() == 1
    assert "You're a seller" in c.get("/account/sell").get_data(as_text=True)
    assert c.post("/account/switch-profile").status_code == 302
    assert c.get("/seller/").status_code == 200  # Seller studio opens
    assert admin.post(f"/admin/seller-requests/{a.id}/approve").status_code == 302  # deciding twice is refused politely
    assert User.query.filter_by(email="sam@example.com#seller").count() == 1


def test_admin_rejects_with_a_note_and_the_buyer_can_apply_again(app, admin):
    c, a = _apply(app)
    admin.post(f"/admin/seller-requests/{a.id}/reject", data={"note": "Please tell us where the watches come from."})
    db.session.expire_all()
    assert db.session.get(SellerApplication, a.id).status == "rejected" and get_user("sam@example.com#seller") is None
    page = c.get("/account/sell").get_data(as_text=True)
    assert "Please tell us where the watches come from." in page and "Send application" in page
    assert 'value="Manila Time House"' in page  # their last answers are filled in again
    c.post("/account/sell", data={**APPLY, "about": "Pre-owned automatics bought from collectors in Manila."})
    assert SellerApplication.query.filter_by(status="pending").count() == 1


def test_admin_can_remove_seller_access(app, admin):
    c, a = _apply(app)
    admin.post(f"/admin/seller-requests/{a.id}/approve")
    s = get_user("sam@example.com#seller")
    admin.post(f"/admin/sellers/{s.id}/revoke")
    db.session.expire_all()
    assert get_user("sam@example.com#seller").is_active_account is False
    assert get_user("sam@example.com").linked_profile is None  # no more "Switch to seller profile"
    assert c.post("/account/switch-profile").status_code == 404
    c2 = app.test_client()
    c2.post("/account/login?as=seller", data={"email": "sam@example.com", "password": "Secret123"})
    assert c2.get("/seller/").status_code == 403  # signs into the buyer account instead
    assert "Apply to sell" in c.get("/account/sell").get_data(as_text=True)  # they could apply again


def test_signing_in_no_longer_creates_seller_profiles(client, app):
    c = app.test_client()
    register(c, "plain@example.com")
    c.post("/account/logout")
    login(c, "plain@example.com", "Secret123")
    assert get_user("plain@example.com#seller") is None


def test_menus_point_buyers_to_the_application(app):
    c = app.test_client()
    register(c, "menu@example.com")
    home = c.get("/").get_data(as_text=True)
    assert 'href="/account/sell"' in home and "Switch to seller profile" not in home
    assert "an admin approves" in app.test_client().get("/account/register").get_data(as_text=True)
