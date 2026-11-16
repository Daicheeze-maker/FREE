"""2 buyers + 2 sellers are connected: each seller profile belongs to its buyer, and orders flow between them."""
import re

from velora import create_app
from velora.cli import demo_status
from velora.extensions import db
from velora.models import Category, Order, OrderStatus, Product, User

from .conftest import default_address, get_user, in_stock_product, login


def _fresh_app(tmp_path, name="demo.db"):
    return create_app("testing", SQLALCHEMY_DATABASE_URI=f"sqlite:///{tmp_path / name}")


# ------------------------------------------------------------ the update prompt

def test_demo_status_recognises_each_kind_of_database(tmp_path):
    from velora.cli import init_database
    from velora.seed import seed
    app = _fresh_app(tmp_path)
    with app.app_context():
        init_database()
        assert demo_status() == "empty"
        seed()
        assert demo_status() == "current"
        Category.query.filter_by(slug="bags").one().slug = "cars"  # what the previous version had
        db.session.commit()
        assert demo_status() == "outdated"
        db.session.delete(User.query.filter_by(email="admin@velora.example").one())  # someone's own store
        db.session.commit()
        assert demo_status() == "custom"


def test_upgrade_demo_replaces_an_outdated_demo_store(tmp_path):
    from velora.cli import init_database
    from velora.seed import seed
    app = _fresh_app(tmp_path)
    with app.app_context():
        init_database()
        seed()
        Category.query.filter_by(slug="bags").one().slug = "cars"
        db.session.commit()
    result = app.test_cli_runner().invoke(args=["upgrade-demo", "--yes"])
    assert result.exit_code == 0 and "new demo store is loaded" in result.output
    with app.app_context():
        assert demo_status() == "current"
        assert Category.query.filter_by(slug="cars").first() is None
        assert [u.email for u in User.query.filter_by(role="customer").order_by(User.id)] == [
            "buyer1@velora.example", "buyer2@velora.example"]


def test_upgrade_demo_never_touches_current_or_custom_stores(tmp_path):
    from velora.cli import init_database
    from velora.seed import seed
    app = _fresh_app(tmp_path)
    with app.app_context():
        init_database()
        seed()
        marker = User(email="marker@example.com", full_name="Marker", role="customer")
        marker.set_password("x")
        db.session.add(marker)
        db.session.commit()
    runner = app.test_cli_runner()
    out = runner.invoke(args=["upgrade-demo", "--yes"]).output
    assert "OLDER VERSION" not in out and "loaded" not in out  # an up-to-date store isn't even mentioned
    with app.app_context():
        assert User.query.filter_by(email="marker@example.com").count() == 1  # current store: untouched
        db.session.delete(User.query.filter_by(email="admin@velora.example").one())
        db.session.commit()
    runner.invoke(args=["upgrade-demo", "--yes"])
    with app.app_context():
        assert User.query.filter_by(email="marker@example.com").count() == 1  # custom store: untouched


def test_upgrade_demo_without_a_keyboard_only_explains(tmp_path):
    from velora.cli import init_database
    from velora.seed import seed
    app = _fresh_app(tmp_path)
    with app.app_context():
        init_database()
        seed()
        Category.query.filter_by(slug="bags").one().slug = "cars"
        db.session.commit()
    out = app.test_cli_runner().invoke(args=["upgrade-demo"]).output  # no --yes and no terminal
    assert "OLDER VERSION" in out and "upgrade-demo" in out
    with app.app_context():
        assert demo_status() == "outdated"  # nothing was deleted


# ------------------------------------------------------ four logins, one click each

def test_sign_in_page_lists_two_buyers_and_two_sellers(client):
    html = client.get("/account/login").get_data(as_text=True)
    assert html.count("data-demo-login") == 5 and html.count('data-as="seller"') == 2
    for text in ("Buyer 1", "Buyer 2", "Seller 1", "Seller 2", "Administrator", "linked to Buyer 1", "linked to Buyer 2"):
        assert text in html


def test_one_click_seller_sign_in_opens_the_linked_seller_profile(client):
    for buyer, name in (("buyer1@velora.example", "Maya"), ("buyer2@velora.example", "Jonah")):
        c = client.application.test_client()
        r = c.post("/account/login?as=seller", data={"email": buyer, "password": "anything"})
        assert r.status_code == 302 and r.headers["Location"].endswith("/seller/")
        html = c.get("/seller/").get_data(as_text=True)
        assert "Store dashboard" in html and name in html
        assert c.get("/account/").status_code == 403  # a seller profile isn't a buyer
        assert c.post("/account/switch-profile").status_code == 302  # ...but its buyer is one click away
        assert "Customer account" in c.get("/account/").get_data(as_text=True)


def test_plain_sign_in_still_opens_the_buyer_profile(client):
    r = client.post("/account/login", data={"email": "buyer1@velora.example", "password": "x"})
    assert r.headers["Location"].endswith("/account/")


# -------------------------------------------- orders flow between connected accounts

def _pay(c, buyer_email):
    page = c.get("/checkout").get_data(as_text=True)
    token = re.search(r'checkout_token[^>]*value="([^"]+)"', page).group(1)
    addr = default_address(get_user(buyer_email))
    return c.post("/checkout", data={"checkout_token": token, "address_choice": str(addr.id)})


def test_buyer_order_reaches_the_linked_seller_and_back(app):
    p = in_stock_product()
    buyer = app.test_client()
    login(buyer, "buyer1@velora.example", "x")
    buyer.post(f"/cart/add/{p.id}", data={"quantity": 1})
    r = _pay(buyer, "buyer1@velora.example")
    assert r.status_code == 302
    order = Order.query.order_by(Order.id.desc()).first()
    assert order.user.email == "buyer1@velora.example" and order.status == OrderStatus.SHIPPED

    # Buyer 1's own seller profile (one click) sees the order and can complete it
    buyer.post("/account/switch-profile")
    assert order.number in buyer.get("/seller/orders").get_data(as_text=True)
    assert buyer.post(f"/seller/orders/{order.number}", data={"status": "delivered"}).status_code == 302

    # ...and back as the buyer: it is delivered, they were notified and can now review the product
    buyer.post("/account/switch-profile")
    html = buyer.get(f"/account/orders/{order.number}").get_data(as_text=True)
    assert "Delivered" in html and "Review" in html
    db.session.expire_all()
    assert any("delivered" in n.title for n in get_user("buyer1@velora.example").notifications)


def test_the_other_seller_shares_the_store_but_the_other_buyer_is_separate(app):
    p = in_stock_product()
    b1 = app.test_client()
    login(b1, "buyer1@velora.example", "x")
    b1.post(f"/cart/add/{p.id}", data={"quantity": 1})
    _pay(b1, "buyer1@velora.example")
    order = Order.query.order_by(Order.id.desc()).first()
    start_b2 = get_user("buyer2@velora.example").balance_minor

    seller2 = app.test_client()  # Jonah's seller profile: one shared store, so it sees every order
    seller2.post("/account/login?as=seller", data={"email": "buyer2@velora.example", "password": "x"})
    assert order.number in seller2.get("/seller/orders").get_data(as_text=True)

    b2 = app.test_client()  # Jonah as a buyer: cannot see Maya's order, and his credit is untouched
    login(b2, "buyer2@velora.example", "x")
    assert b2.get(f"/account/orders/{order.number}").status_code == 404
    db.session.expire_all()
    assert get_user("buyer2@velora.example").balance_minor == start_b2 == 50_000_000
    assert get_user("buyer1@velora.example").balance_minor == 50_000_000 - order.total_minor


def test_each_buyer_has_their_own_credit_and_addresses(app):
    b1, b2 = get_user("buyer1@velora.example"), get_user("buyer2@velora.example")
    assert b1.balance_minor == b2.balance_minor == 50_000_000
    assert b1.addresses and b2.addresses
    assert {a.id for a in b1.addresses}.isdisjoint({a.id for a in b2.addresses})
    assert b1.linked_profile.email == "buyer1@velora.example#seller"
    assert b2.linked_profile.email == "buyer2@velora.example#seller"
    assert b1.linked_profile.linked_profile == b1  # the link goes both ways


def test_account_menu_shows_the_buyers_credit_but_not_the_sellers(app):
    b = app.test_client()
    login(b, "buyer1@velora.example", "x")
    assert "Credit ₱500,000.00" in b.get("/").get_data(as_text=True)
    b.post("/account/switch-profile")
    assert "Credit ₱" not in b.get("/seller/").get_data(as_text=True)  # credit belongs to the buyer profile
