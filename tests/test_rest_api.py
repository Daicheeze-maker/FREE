"""The REST API (/api/v1): methods, JSON payloads, status codes and error handling."""
from unittest.mock import patch

import requests

from velora.extensions import db
from velora.models import Order, Product, User

from .conftest import get_user, in_stock_product, optioned_product

BUYER = ("buyer1@velora.example", "Buyer123!")
ADMIN = ("admin@velora.example", "Admin123!")
ADDRESS = {"full_name": "Juan Dela Cruz", "phone": "09171234567", "phone_country": "PH", "line1": "12 Rizal St",
           "city": "Naga City", "region": "Camarines Sur", "postal_code": "4400"}


def token(client, who=BUYER):
    r = client.post("/api/v1/auth/token", json={"email": who[0], "password": who[1]})
    assert r.status_code == 200, r.get_json()
    return {"Authorization": f"Bearer {r.get_json()['token']}"}


# ---------------------------------------------------------------- index, docs, health

def test_index_lists_every_endpoint_and_the_list_matches_the_routes(client, app):
    data = client.get("/api/v1").get_json()
    assert data["version"] == "v1" and len(data["endpoints"]) >= 20
    rules = {(m, r.rule) for r in app.url_map.iter_rules() if r.rule.startswith("/api/v1") for m in r.methods}
    for e in data["endpoints"]:
        path = (e["path"].replace("<id or slug>", "<ref>").replace("<id>", "<int:x>").replace("<number>", "<number>"))
        matched = any(m == e["method"] and _same(rule, path) for m, rule in rules)
        assert matched, e


def _same(rule, path):
    import re
    norm = lambda s: re.sub(r"<[^>]+>", "<x>", s)
    return norm(rule) == norm(path)


def test_docs_page_and_health(client):
    html = client.get("/api/docs").get_data(as_text=True)
    assert "REST API" in html and "/api/v1/orders" in html and "Bearer" in html
    h = client.get("/api/v1/health")
    assert h.status_code == 200 and h.get_json()["database"]["ok"] is True and h.get_json()["database"]["products"] == 60


def test_unknown_route_and_wrong_method_answer_in_json(client):
    r = client.get("/api/v1/nothing-here")
    assert r.status_code == 404 and r.get_json()["error"]["code"] == "not_found"
    r = client.put("/api/v1/products")
    assert r.status_code == 405 and r.get_json()["error"]["code"] == "method_not_allowed"


# ---------------------------------------------------------------- auth

def test_token_errors_and_success(client):
    assert client.post("/api/v1/auth/token", json={}).status_code == 422
    r = client.post("/api/v1/auth/token", json={"email": BUYER[0], "password": "wrong"})
    assert r.status_code == 401 and r.get_json()["error"]["code"] == "invalid_credentials"
    r = client.post("/api/v1/auth/token", data="email=x", content_type="application/x-www-form-urlencoded")
    assert r.status_code == 415
    r = client.post("/api/v1/auth/token", data="{bad json", content_type="application/json")
    assert r.status_code == 400 and r.get_json()["error"]["code"] == "bad_json"
    h = token(client)
    me = client.get("/api/v1/me", headers=h).get_json()
    assert me["email"] == BUYER[0] and me["role"] == "customer" and me["demo_credit"]["minor"] == 50_000_000


def test_protected_endpoints_need_a_valid_token(client):
    r = client.get("/api/v1/cart")
    assert r.status_code == 401 and r.headers["WWW-Authenticate"].startswith("Bearer")
    r = client.get("/api/v1/cart", headers={"Authorization": "Bearer not-a-token"})
    assert r.status_code == 401 and r.get_json()["error"]["code"] == "invalid_token"


def test_the_website_cookie_never_counts_for_the_api(client):
    client.post("/account/login", data={"email": BUYER[0], "password": BUYER[1]})
    assert client.get("/account/").status_code == 200  # signed in on the website...
    assert client.get("/api/v1/cart").status_code == 401  # ...but the API wants its own token (no CSRF risk)


def test_changing_the_password_signs_tokens_out(client):
    h = token(client)
    user = get_user(BUYER[0])
    user.set_password("NewPass123!")
    db.session.commit()
    assert client.get("/api/v1/me", headers=h).status_code == 401


# ---------------------------------------------------------------- catalog

def test_products_list_filters_and_pagination(client):
    data = client.get("/api/v1/products?category=dive-watches&per_page=4&page=2").get_json()
    assert data["total"] == 10 and data["page"] == 2 and len(data["items"]) == 4 and data["pages"] == 3
    assert all(p["category"] == "dive-watches" for p in data["items"])
    cheap = client.get("/api/v1/products?max_price=8000&sort=price_asc").get_json()["items"]
    assert cheap and all(p["price"]["minor"] <= 800000 for p in cheap)
    assert [p["price"]["minor"] for p in cheap] == sorted(p["price"]["minor"] for p in cheap)
    assert client.get("/api/v1/products?category=shoes").status_code == 404
    assert client.get("/api/v1/products?sort=random").status_code == 400
    assert client.get("/api/v1/products?min_price=abc").status_code == 400
    cats = client.get("/api/v1/categories").get_json()["items"]
    assert len(cats) == 6 and all(c["product_count"] == 10 for c in cats)


def test_product_detail_by_id_or_slug(client):
    p = Product.query.filter_by(slug="riviera-blue-chrono-41").one()
    a = client.get(f"/api/v1/products/{p.id}").get_json()
    b = client.get("/api/v1/products/riviera-blue-chrono-41").get_json()
    assert a == b and a["sizes"] == ["39 mm", "41 mm"] and a["colors"] == ["Blue"] and a["engraving"]["fee"]["minor"] == 60000
    assert client.get("/api/v1/products/no-such-watch").status_code == 404


# ---------------------------------------------------------------- product CRUD (staff)

def test_staff_create_update_archive_a_product(client):
    h = token(client, ADMIN)
    body = {"name": "Test Field 40", "brand": "Aurelune", "category": "field-pilot", "price": 9900, "stock": 5,
            "short_description": "Test", "description": "A test watch.", "sizes": ["38 mm", "40 mm"], "colors": "Black"}
    r = client.post("/api/v1/products", json=body, headers=h)
    assert r.status_code == 201, r.get_json()
    made = r.get_json()
    assert r.headers["Location"].endswith(f"/api/v1/products/{made['id']}") and made["slug"] == "test-field-40"
    assert made["price"]["minor"] == 990000 and made["sizes"] == ["38 mm", "40 mm"]
    r = client.patch(f"/api/v1/products/{made['id']}", json={"price": 8900, "stock": 2}, headers=h)
    assert r.status_code == 200 and r.get_json()["price"]["minor"] == 890000 and r.get_json()["stock"] == 2
    assert client.delete(f"/api/v1/products/{made['id']}", headers=h).status_code == 204
    assert client.get(f"/api/v1/products/{made['id']}").status_code == 404  # archived: gone from the shop
    assert db.session.get(Product, made["id"]).status == "archived"  # but kept for order history


def test_product_validation_lists_every_bad_field(client):
    h = token(client, ADMIN)
    r = client.post("/api/v1/products", json={"name": "x", "price": -5, "stock": "lots", "category": "shoes"}, headers=h)
    err = r.get_json()["error"]
    assert r.status_code == 422 and err["code"] == "validation_failed"
    assert {"name", "price", "stock", "category", "brand", "description"} <= set(err["fields"])
    assert Product.query.filter_by(name="x").count() == 0


def test_buyers_cannot_change_products(client):
    r = client.post("/api/v1/products", json={"name": "Nope"}, headers=token(client))
    assert r.status_code == 403 and r.get_json()["error"]["code"] == "forbidden"


# ---------------------------------------------------------------- cart and orders: the whole journey

def test_full_journey_cart_order_status_and_history(client):
    h = token(client)
    p = optioned_product()
    size, color = p.size_list[0], p.color_list[0]
    r = client.post("/api/v1/cart/items", json={"product_id": p.id, "quantity": 2, "size": size, "color": color,
                                                "engraving": "MJ"}, headers=h)
    assert r.status_code == 201, r.get_json()
    cart = r.get_json()
    line = cart["items"][0]
    assert cart["count"] == 2 and line["engraving"] == "MJ"
    assert line["unit_price"]["minor"] == p.price_minor + p.engraving_fee_minor
    r = client.patch(f"/api/v1/cart/items/{line['id']}", json={"quantity": 1}, headers=h)
    assert r.status_code == 200 and r.get_json()["count"] == 1
    stock_before = p.stock
    r = client.post("/api/v1/orders", json={"address": ADDRESS, "notes": "Leave at the gate"},
                    headers={**h, "Idempotency-Key": "test-order-1"})
    assert r.status_code == 201, r.get_json()
    order = r.get_json()
    assert order["ship_to"]["phone"] == "+639171234567" and order["items"][0]["quantity"] == 1
    assert order["payment"]["status"] == "succeeded" and order["status"] == "shipped"
    again = client.post("/api/v1/orders", json={"address": ADDRESS}, headers={**h, "Idempotency-Key": "test-order-1"})
    assert again.status_code == 200 and again.get_json()["number"] == order["number"]  # a retry never orders twice
    assert Order.query.filter_by(checkout_token="test-order-1").count() == 1
    db.session.expire_all()
    assert db.session.get(Product, p.id).stock == stock_before - 1
    assert client.get("/api/v1/cart", headers=h).get_json()["count"] == 0
    history = client.get("/api/v1/orders", headers=h).get_json()
    assert history["items"][0]["number"] == order["number"]  # newest first
    assert client.get(f"/api/v1/orders/{order['number']}", headers=h).status_code == 200
    # the buyer can't move it along; staff can, but only along the allowed steps
    assert client.patch(f"/api/v1/orders/{order['number']}", json={"status": "delivered"}, headers=h).status_code == 403
    staff = token(client, ADMIN)
    r = client.patch(f"/api/v1/orders/{order['number']}", json={"status": "pending"}, headers=staff)
    assert r.status_code == 409 and r.get_json()["error"]["code"] == "invalid_transition"
    r = client.patch(f"/api/v1/orders/{order['number']}", json={"status": "delivered"}, headers=staff)
    assert r.status_code == 200 and r.get_json()["status"] == "delivered"
    r = client.post(f"/api/v1/orders/{order['number']}/cancel", json={}, headers=h)
    assert r.status_code == 409 and r.get_json()["error"]["code"] == "cannot_cancel"


def test_edge_cases_empty_bag_sold_out_bad_options_and_other_peoples_orders(client):
    h = token(client)
    r = client.post("/api/v1/orders", json={"address": ADDRESS}, headers=h)
    assert r.status_code == 409 and "empty" in r.get_json()["error"]["message"]
    p = in_stock_product()
    p.stock = 0
    db.session.commit()
    r = client.post("/api/v1/cart/items", json={"product_id": p.id}, headers=h)
    assert r.status_code == 409 and r.get_json()["error"]["code"] == "out_of_stock"
    q = optioned_product()
    r = client.post("/api/v1/cart/items", json={"product_id": q.id, "size": "99 mm", "color": q.color_list[0]}, headers=h)
    assert r.status_code == 422 and r.get_json()["error"]["code"] == "invalid_options"
    r = client.post("/api/v1/cart/items", json={"product_id": q.id, "quantity": 0}, headers=h)
    assert r.status_code == 422
    assert client.patch("/api/v1/cart/items/999999", json={"quantity": 1}, headers=h).status_code == 404
    r = client.post("/api/v1/orders", json={"address": {**ADDRESS, "phone": "123"}}, headers=h)
    assert r.status_code == 422 and "address.phone" in r.get_json()["error"]["fields"]
    # someone else's order looks exactly like a missing one
    other = User.query.filter_by(email="buyer2@velora.example").one()
    theirs = Order.query.filter_by(user_id=other.id).first()
    if theirs is not None:
        assert client.get(f"/api/v1/orders/{theirs.number}", headers=h).status_code == 404


def test_not_enough_credit_is_a_conflict(client):
    h = token(client)
    user = get_user(BUYER[0])
    user.balance_minor = 100
    db.session.commit()
    p = in_stock_product()
    client.post("/api/v1/cart/items", json={"product_id": p.id}, headers=h)
    r = client.post("/api/v1/orders", json={"address": ADDRESS}, headers=h)
    assert r.status_code == 409 and "demo credit" in r.get_json()["error"]["message"]


# ---------------------------------------------------------------- outside APIs through this API

def test_rates_come_from_frankfurter_and_fail_gracefully(client):
    class Resp:
        status_code = 200
        def raise_for_status(self): pass
        def json(self): return {"base": "PHP", "date": "2026-11-20", "rates": {"USD": 0.017, "EUR": 0.0158, "GBP": 0.0134,
                                                                           "JPY": 2.61, "SGD": 0.0228, "AUD": 0.026}}
    with patch("velora.services.currency.requests.get", return_value=Resp()):
        r = client.get("/api/v1/rates")
    assert r.status_code == 200 and r.get_json()["rates"]["USD"]["rate"] == "0.017"
    from velora.models import ExchangeRateCache
    ExchangeRateCache.query.delete()
    db.session.commit()
    with patch("velora.services.currency.requests.get", side_effect=requests.Timeout("slow")):
        r = client.get("/api/v1/rates")
    assert r.status_code == 503 and r.get_json()["error"]["code"] == "rates_unavailable" and "Retry-After" in r.headers


def test_reverse_geocode_validates_and_reports_timeouts(client):
    h = token(client)
    assert client.get("/api/v1/geocode/reverse?lat=13.6", headers=h).status_code == 400
    assert client.get("/api/v1/geocode/reverse?lat=200&lng=5", headers=h).status_code == 422
    with patch("velora.services.nominatim.requests.get", side_effect=requests.Timeout("slow")):
        r = client.get("/api/v1/geocode/reverse?lat=13.62&lng=123.19", headers=h)
    assert r.status_code == 504 and r.get_json()["error"]["code"] == "upstream_timeout"
    with patch("velora.services.nominatim.requests.get", side_effect=requests.ConnectionError("down")):
        r = client.get("/api/v1/geocode/reverse?lat=13.62&lng=123.19", headers=h)
    assert r.status_code == 502

    class Resp:
        def raise_for_status(self): pass
        def json(self): return {"display_name": "Naga", "lat": "13.62", "lon": "123.19",
                                "address": {"road": "Rizal St", "city": "Naga", "state": "Camarines Sur",
                                            "postcode": "4400", "country": "Philippines"}}
    with patch("velora.services.nominatim.requests.get", return_value=Resp()):
        r = client.get("/api/v1/geocode/reverse?lat=13.62&lng=123.19", headers=h)
    assert r.status_code == 200 and r.get_json()["source"] == "OpenStreetMap Nominatim"
    assert r.get_json()["result"]["city"] == "Naga"
