"""No demo accounts, Mapbox address suggestions, the home-page photos and the shop-page menu."""
import html
import re
from unittest.mock import patch

import pytest
import requests

from velora import create_app
from velora.cli import demo_status, remove_demo_accounts
from velora.extensions import db
from velora.models import Notification, Order, StoreSetting, User
from velora.seed import seed

from .conftest import IsolatedClient, get_user, in_stock_product, login

TOKEN = "pk.eyJ1IjoidGVzdCIsImEiOiJhYmNkZWZnaGlqa2xtbm9wcXJzdHV2In0.abcdefghijklmnop"


class Resp:
    def __init__(self, status=200, data=None):
        self.status_code, self._data = status, data if data is not None else {}

    def json(self):
        return self._data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(str(self.status_code))


FEATURE = {"geometry": {"coordinates": [121.0244, 14.5547]},
           "properties": {"name": "6750 Ayala Avenue", "full_address": "6750 Ayala Avenue, Makati, Metro Manila 1226, Philippines",
                          "context": {"address": {"name": "6750 Ayala Avenue"}, "postcode": {"name": "1226"},
                                      "place": {"name": "Makati"}, "region": {"name": "Metro Manila"},
                                      "country": {"name": "Philippines"}, "neighborhood": {"name": "San Lorenzo"}}}}


def mapbox_get(status=200, features=(FEATURE,), error=None):
    calls = []

    def fake(url, **kw):
        calls.append((url, kw))
        if error:
            raise error
        return Resp(status, {"features": list(features)})
    return patch("velora.services.mapbox.requests.get", side_effect=fake), calls


@pytest.fixture()
def fresh(tmp_path):
    """A brand-new store exactly as start.bat creates it (no demo accounts)."""
    app = create_app("testing", SQLALCHEMY_DATABASE_URI=f"sqlite:///{tmp_path / 'fresh.db'}", UPLOAD_FOLDER=str(tmp_path / "u"))
    app.test_client_class = IsolatedClient
    with app.app_context():
        db.create_all()
        assert seed() is True
        yield app
        db.session.remove()


# ------------------------------------------------------------------ no demo accounts

def test_fresh_store_has_no_accounts_orders_or_demo_logins(fresh):
    assert User.query.count() == 0 and Order.query.count() == 0
    page = fresh.test_client().get("/account/login").get_data(as_text=True)
    assert "velora.example" not in page and "Demo accounts" not in page and "data-demo-login" not in page
    assert demo_status() == "current"


def test_account_created_on_the_site_is_saved_in_the_database(fresh):
    c = fresh.test_client()
    r = c.post("/account/register", data={"full_name": "Real Buyer", "email": "Real@Example.com", "password": "Secret123",
                                          "confirm": "Secret123", "accept": "y"})
    assert r.status_code == 302
    db.session.expire_all()
    u = get_user("real@example.com")
    assert u and u.balance_minor == 50_000_000 and get_user("real@example.com#seller")
    assert Notification.query.filter_by(user_id=u.id).count() == 1
    # a different browser (new client) signs in with the saved password, and only that password
    other = fresh.test_client()
    assert login(other, "real@example.com", "nope").status_code == 200
    assert login(other, "real@example.com", "Secret123").status_code == 302


def test_old_sample_accounts_are_removed_but_real_ones_kept(app):
    # `app` has the sample people + seeded orders (tests only)
    assert get_user("buyer1@velora.example")
    real = get_user("buyer2@velora.example")
    db.session.add(Order(number="VM-REAL-1", user_id=real.id, checkout_token="real-token", ship_name="x", ship_phone="1",
                         ship_address="y", subtotal_minor=1, total_minor=1))
    db.session.commit()
    removed, kept = remove_demo_accounts()
    assert "buyer1@velora.example" in removed and "admin@velora.example" in removed
    assert "buyer2@velora.example" in kept
    db.session.expire_all()
    assert get_user("buyer1@velora.example") is None and get_user("buyer1@velora.example#seller") is None
    assert get_user("buyer2@velora.example") is not None


def test_upgrade_demo_command_removes_old_sample_accounts(tmp_path):
    from velora.cli import init_database
    app = create_app("testing", SQLALCHEMY_DATABASE_URI=f"sqlite:///{tmp_path / 'old.db'}")
    with app.app_context():
        init_database()
        seed(demo_accounts=True)  # what an older release left behind
        assert User.query.count() == 5
    out = app.test_cli_runner().invoke(args=["upgrade-demo"]).output
    assert "Removed 5 old sample account(s)" in out
    with app.app_context():
        assert User.query.count() == 0 and Order.query.count() == 0


# ------------------------------------------------------------------ Mapbox

def test_address_search_needs_login_and_token(app, client):
    assert client.get("/address-search?q=ayala").status_code == 302
    login(client, "buyer1@velora.example", "Buyer123!")
    data = client.get("/address-search?q=ayala").get_json()
    assert data["ok"] is False and data["results"] == []


def test_address_search_returns_clean_fields_and_hides_token(app, client):
    app.config["MAPBOX_TOKEN"] = TOKEN
    login(client, "buyer1@velora.example", "Buyer123!")
    p, calls = mapbox_get()
    with p:
        r = client.get("/address-search?q=6750 Ayala")
    data = r.get_json()
    assert data["ok"] and data["results"][0] == {
        "label": "6750 Ayala Avenue, Makati, Metro Manila 1226, Philippines", "line1": "6750 Ayala Avenue",
        "line2": "San Lorenzo", "city": "Makati", "region": "Metro Manila", "postal_code": "1226",
        "country": "Philippines", "lat": 14.5547, "lng": 121.0244}
    assert TOKEN not in r.get_data(as_text=True)
    url, kw = calls[0]
    assert url.startswith("https://api.mapbox.com/search/geocode/v6/forward")
    assert kw["params"]["q"] == "6750 Ayala" and kw["params"]["country"] == "ph"


def test_address_search_short_query_makes_no_call(app, client):
    app.config["MAPBOX_TOKEN"] = TOKEN
    login(client, "buyer1@velora.example", "Buyer123!")
    p, calls = mapbox_get()
    with p:
        assert client.get("/address-search?q=ab").get_json()["results"] == []
    assert calls == []


@pytest.mark.parametrize("kw", [{"status": 401}, {"status": 429}, {"error": requests.ConnectionError("down")}])
def test_address_search_degrades_gracefully(app, client, kw):
    app.config["MAPBOX_TOKEN"] = TOKEN
    login(client, "buyer1@velora.example", "Buyer123!")
    p, _ = mapbox_get(**kw)
    with p:
        r = client.get("/address-search?q=ayala avenue")
    assert r.status_code == 200 and r.get_json()["ok"] is False and r.get_json()["results"] == []


def test_checkout_address_form_only_offers_suggestions_when_token_is_set(app, client):
    login(client, "buyer1@velora.example", "Buyer123!")
    client.post(f"/cart/add/{in_stock_product().id}", data={"quantity": 1})
    assert "data-address-search" not in client.get("/checkout").get_data(as_text=True)
    app.config["MAPBOX_TOKEN"] = TOKEN
    page = client.get("/checkout").get_data(as_text=True)
    assert 'data-address-search="/address-search"' in page and "address-search.js" in page


def test_admin_saves_only_a_working_token(admin, app):
    r, _ = mapbox_get(status=401)
    with r:
        admin.post("/admin/mapbox-token", data={"token": TOKEN})
    assert db.session.get(StoreSetting, "mapbox_token") is None
    admin.post("/admin/mapbox-token", data={"token": "not a token"})
    assert db.session.get(StoreSetting, "mapbox_token") is None
    r, _ = mapbox_get()
    with r:
        admin.post("/admin/mapbox-token", data={"token": TOKEN})
    db.session.expire_all()
    assert db.session.get(StoreSetting, "mapbox_token").value == TOKEN
    page = admin.get("/admin/api-health").get_data(as_text=True)
    assert "Mapbox" in page and TOKEN not in page
    admin.post("/admin/mapbox-token", data={"action": "remove"})
    db.session.expire_all()
    assert db.session.get(StoreSetting, "mapbox_token") is None


def test_customer_cannot_set_the_mapbox_token(customer):
    assert customer.post("/admin/mapbox-token", data={"token": TOKEN}).status_code in (302, 403)
    assert db.session.get(StoreSetting, "mapbox_token") is None


# ------------------------------------------------------------------ home page photos

def test_home_page_has_real_photos_not_the_placeholder(client):
    page = client.get("/").get_data(as_text=True)
    for slot_class in ("hero__photo", "aisles__intro"):
        chunk = page.split(slot_class)[1][:400]
        assert "model-placeholder" not in chunk, slot_class
    assert "model-placeholder" not in page.split("hero__photo")[1].split("</div>")[0]
    assert re.search(r'hero__photo"><img src="https://images\.unsplash\.com/', page)


def test_site_photo_falls_back_to_placeholder_when_catalog_has_no_photo(client):
    from velora.models import ProductImage
    ProductImage.query.delete()
    db.session.commit()
    assert "model-placeholder" in client.get("/").get_data(as_text=True).split("hero__photo")[1][:300]


# ------------------------------------------------------------------ shop-page menu

def _nav(page):
    return page.split('class="header__nav"')[1].split("</nav>")[0]


def test_top_menu_is_hidden_on_shop_pages_but_shown_elsewhere(client):
    shop = client.get("/shop/c/jewelry").get_data(as_text=True)
    assert "hidden>" in shop.split('class="header__nav"')[1][:60] and "Watches" not in _nav(shop)
    assert "Collections" in shop  # the left list is how you move between collections there
    for url in ("/", "/about"):
        page = client.get(url).get_data(as_text=True)
        assert all(w in _nav(page) for w in ("Clothing", "Watches", "Jewelry", "Bags")), url


# ------------------------------------------------------------------ sign-in layout, pin map, stale links

def test_sign_in_and_register_have_back_button_and_the_other_link_at_the_bottom(client):
    login_page = client.get("/account/login").get_data(as_text=True)
    assert "data-back" in login_page and "auth__alt" in login_page
    assert login_page.index("auth__alt") > login_page.index("</form>")
    assert 'href="/account/register"' in login_page.split("auth__alt")[1]
    reg = client.get("/account/register").get_data(as_text=True)
    assert "data-back" in reg and 'href="/account/login"' in reg.split("auth__alt")[1]
    assert "model-placeholder" not in login_page.split("auth__art")[1][:300]


def test_error_page_has_a_back_button(client):
    page = client.get("/nope-nothing-here").get_data(as_text=True)
    assert "data-back" in page


def test_checkout_and_address_pages_have_the_pin_map(app, client):
    login(client, "buyer1@velora.example", "Buyer123!")
    client.post(f"/cart/add/{in_stock_product().id}", data={"quantity": 1})
    for url in ("/checkout", "/account/addresses"):
        page = client.get(url).get_data(as_text=True)
        assert "data-pin-map" in page and "pin-map.js" in page and "leaflet.js" in page, url
        assert 'data-reverse="/address-reverse"' in page
    assert "data-back" in client.get("/checkout").get_data(as_text=True)


def test_address_reverse_turns_a_pin_into_an_address(app, client):
    assert client.get("/address-reverse?lat=14.55&lng=121.02").status_code == 302  # signed in only
    login(client, "buyer1@velora.example", "Buyer123!")
    assert client.get("/address-reverse?lat=14.55&lng=121.02").get_json()["error"] == "no_token"
    assert client.get("/address-reverse?lat=abc&lng=1").status_code == 400
    app.config["MAPBOX_TOKEN"] = TOKEN
    p, calls = mapbox_get()
    with p:
        data = client.get("/address-reverse?lat=14.5547&lng=121.0244").get_json()
        assert data["ok"] and data["result"]["city"] == "Makati" and data["result"]["postal_code"] == "1226"
        assert client.get("/address-reverse?lat=999&lng=1").get_json()["ok"] is False  # out of range, no crash
    assert calls[0][0].endswith("/search/geocode/v6/reverse")
    assert calls[0][1]["params"]["latitude"] == 14.5547 and calls[0][1]["params"]["longitude"] == 121.0244
    p, _ = mapbox_get(features=())
    with p:
        assert client.get("/address-reverse?lat=1&lng=1").get_json() == {"ok": True, "result": None}


def test_stale_next_link_does_not_land_on_a_404_after_signing_in(client):
    r = client.post("/account/login?next=/shop/c/cars-that-are-gone", data={"email": "buyer1@velora.example", "password": "Buyer123!"})
    assert r.headers["Location"].endswith("/account/")
    client.post("/account/logout")
    r = client.post("/account/login?next=/shop/c/bags", data={"email": "buyer1@velora.example", "password": "Buyer123!"})
    assert r.headers["Location"].endswith("/shop/c/bags")
