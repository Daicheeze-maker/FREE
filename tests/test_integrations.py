"""External APIs are always mocked here — the suite never needs network access."""
from decimal import Decimal
from unittest.mock import MagicMock, patch

import requests

from velora.extensions import db
from velora.models import ApiStatus, ExchangeRateCache, Product, utcnow
from velora.money import convert, fmt_minor, to_minor
from velora.services import currency, openfoodfacts as off


def fake_response(payload, status=200):
    r = MagicMock()
    r.status_code = status
    r.json.return_value = payload
    r.raise_for_status.side_effect = None if status < 400 else requests.HTTPError(f"{status}")
    return r


FX_PAYLOAD = {"amount": 1.0, "base": "PHP", "date": "2026-10-29",
              "rates": {"USD": 0.01712, "EUR": 0.01578, "GBP": 0.01321, "JPY": 2.6194, "SGD": 0.02251, "AUD": 0.02618}}


# ------------------------------------------------------------------ money

def test_money_helpers_use_decimal():
    assert to_minor("1,299.50") == 129950
    assert to_minor("0.005") == 1  # half-up
    assert fmt_minor(129950) == "₱1,299.50"
    assert convert(100000, Decimal("0.01712"), "USD") == Decimal("17.12")
    assert convert(100000, Decimal("2.6194"), "JPY") == Decimal("2619")


# --------------------------------------------------------------- Frankfurter

def test_frankfurter_fetch_and_cache(app):
    with patch("velora.services.currency.requests.get", return_value=fake_response(FX_PAYLOAD)) as g:
        q = currency.get_quote("USD")
        assert q.rate == Decimal("0.01712") and q.rate_date == "2026-10-29" and not q.stale
        currency.get_quote("EUR")  # served from cache
        assert g.call_count == 1
        args, kwargs = g.call_args
        assert args[0].endswith("/latest") and kwargs["params"]["base"] == "PHP"
        assert "VeloraMarket" in kwargs["headers"]["User-Agent"]
    assert ExchangeRateCache.query.count() == 6
    assert ApiStatus.query.filter_by(name="frankfurter").first().success_count == 1


def test_converted_prices_displayed(client):
    with patch("velora.services.currency.requests.get", return_value=fake_response(FX_PAYLOAD)):
        client.post("/currency", data={"currency": "USD", "next": "/"})
        html = client.get("/shop/").get_data(as_text=True)
    assert "≈ $" in html


def test_currency_falls_back_to_base_when_api_down(client):
    with patch("velora.services.currency.requests.get", side_effect=requests.ConnectionError("offline")):
        client.post("/currency", data={"currency": "EUR", "next": "/"})
        html = client.get("/").get_data(as_text=True)
    assert "₱" in html and "≈ €" not in html
    assert "unavailable right now" in html
    st = ApiStatus.query.filter_by(name="frankfurter").first()
    assert st.error_count >= 1 and "offline" in st.last_error


def test_stale_cache_used_when_api_down(app):
    db.session.add(ExchangeRateCache(base="PHP", target="USD", rate="0.0170", rate_date="2026-01-01",
                                     fetched_at=utcnow().replace(year=2025)))
    db.session.commit()
    with patch("velora.services.currency.requests.get", side_effect=requests.Timeout("slow")):
        q = currency.get_quote("USD")
    assert q.rate == Decimal("0.0170") and q.stale


def test_malformed_fx_response_rejected(app):
    with patch("velora.services.currency.requests.get", return_value=fake_response({"rates": {"USD": -1}})):
        assert currency.get_quote("USD") is None


def test_invalid_currency_ignored(client):
    client.post("/currency", data={"currency": "XXX"})
    with client.session_transaction() as s:
        assert s.get("currency") is None


def test_orders_always_charged_in_base_currency(customer):
    from tests.test_checkout_orders import _checkout
    from velora.models import Order
    from tests.conftest import in_stock_product
    with patch("velora.services.currency.requests.get", return_value=fake_response(FX_PAYLOAD)):
        customer.post("/currency", data={"currency": "USD"})
        p = in_stock_product()
        customer.post(f"/cart/add/{p.id}", data={"quantity": 1})
        _checkout(customer)
    o = Order.query.order_by(Order.id.desc()).first()
    assert o.currency == "PHP" and o.subtotal_minor == p.price_minor


# ---------------------------------------------------------- Open Food Facts

OFF_RAW = {
    "code": "3017624010701", "product_name": "  Nutella  ", "brands": "Ferrero,Nutella",
    "categories": "Spreads, Sweet spreads", "quantity": "400 g",
    "image_front_url": "http://images.openfoodfacts.org/images/products/301/762/401/0701/front_en.jpg",
    "ingredients_text": "Sugar, palm oil, hazelnuts 13%, skimmed milk powder 8.7%, cocoa",
    "allergens": "en:milk,en:nuts", "nutriscore_grade": "e",
    "nutriments": {"energy-kcal_100g": 539, "fat_100g": 30.9, "sugars_100g": "56.3", "proteins_100g": None, "salt_100g": "abc"},
}


def test_off_normalize_handles_messy_data():
    p = off.normalize(OFF_RAW)
    assert p.name == "Nutella" and p.brand == "Ferrero" and p.nutriscore == "e"
    assert p.image_url.startswith("https://")
    assert p.nutrition["sugars_100g"]["value"] == 56.3
    assert "proteins_100g" not in p.nutrition and "salt_100g" not in p.nutrition
    assert p.allergens == "milk, nuts"


def test_off_normalize_rejects_unusable():
    assert off.normalize({"code": "abc", "product_name": "X"}) is None
    assert off.normalize({"code": "12345678"}) is None
    minimal = off.normalize({"code": "12345678", "product_name": "Plain oats"})
    assert minimal and minimal.image_url is None and minimal.nutrition == {}


def test_off_search_parses_results(app):
    payload = {"count": 2, "page": 1, "products": [OFF_RAW, {"code": "bad"}]}
    with patch("velora.services.openfoodfacts.requests.get", return_value=fake_response(payload)) as g:
        results, count = off.search("nutella")
    assert count == 2 and len(results) == 1
    assert g.call_args.kwargs["params"]["search_terms"] == "nutella"
    assert "VeloraMarket" in g.call_args.kwargs["headers"]["User-Agent"]


def test_off_search_page_and_error_state(seller):
    payload = {"count": 1, "products": [OFF_RAW]}
    with patch("velora.services.openfoodfacts.requests.get", return_value=fake_response(payload)):
        html = seller.get("/seller/import?q=nutella").get_data(as_text=True)
    assert "Nutella" in html and "3017624010701" in html
    with patch("velora.services.openfoodfacts.requests.get", side_effect=requests.ConnectionError("dns")):
        html = seller.get("/seller/import?q=nutella").get_data(as_text=True)
    assert "Couldn&#39;t reach Open Food Facts" in html or "Couldn't reach Open Food Facts" in html


def test_off_rate_limit_reported(app):
    with patch("velora.services.openfoodfacts.requests.get", return_value=fake_response({}, status=429)):
        try:
            off.search("oats")
            assert False, "expected OFFUnavailable"
        except off.OFFUnavailable as exc:
            assert "rate limit" in str(exc)


def test_off_import_fetches_authoritative_data(seller):
    product_payload = {"status": 1, "code": "3017624010701", "product": OFF_RAW}
    with patch("velora.services.openfoodfacts.requests.get", return_value=fake_response(product_payload)):
        r = seller.post("/seller/import", data={"barcode": "3017624010701", "category_id": 2, "price": "299.00",
                                                "stock": 12, "name": "INJECTED NAME"})
    assert r.status_code == 302
    p = Product.query.filter_by(off_barcode="3017624010701").first()
    assert p.name == "Nutella" and p.price_minor == 29900 and p.status == "draft"
    assert p.source == "openfoodfacts" and p.nutrition_json and p.images[0].url.startswith("https://")
    # duplicate import blocked
    with patch("velora.services.openfoodfacts.requests.get", return_value=fake_response(product_payload)):
        seller.post("/seller/import", data={"barcode": "3017624010701", "category_id": 2, "price": "1", "stock": 1})
    assert Product.query.filter_by(off_barcode="3017624010701").count() == 1


def test_off_import_unknown_barcode(seller):
    with patch("velora.services.openfoodfacts.requests.get", return_value=fake_response({"status": 0})):
        r = seller.post("/seller/import", data={"barcode": "00000000", "category_id": 1, "price": "10", "stock": 1}, follow_redirects=True)
    assert "no product with that barcode" in r.get_data(as_text=True)


def test_imported_product_visible_offline(client, app):
    product_payload = {"status": 1, "code": "3017624010701", "product": OFF_RAW}
    from velora.models import Category
    with app.test_request_context():
        with patch("velora.services.openfoodfacts.requests.get", return_value=fake_response(product_payload)):
            p = off.import_product("3017624010701", Category.query.first(), 25000, 5, status="active")
        db.session.commit()
    with patch("velora.services.openfoodfacts.requests.get", side_effect=AssertionError("no network!")):
        html = client.get(f"/shop/p/{p.slug}").get_data(as_text=True)
    assert "Nutri-Score" in html and "hazelnuts" in html


def test_admin_api_health_page(admin):
    with patch("velora.services.currency.requests.get", return_value=fake_response(FX_PAYLOAD)):
        r = admin.post("/admin/api-health/frankfurter/test", follow_redirects=True)
    assert "Frankfurter OK" in r.get_data(as_text=True)
    with patch("velora.services.openfoodfacts.requests.get", side_effect=requests.ConnectionError("down")):
        r = admin.post("/admin/api-health/openfoodfacts/test", follow_redirects=True)
    html = r.get_data(as_text=True)
    assert "Open Food Facts unavailable" in html and "Last call failed" in html
