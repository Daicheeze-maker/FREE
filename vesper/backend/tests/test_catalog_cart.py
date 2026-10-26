from sqlalchemy import func, select

from app.models import Product, Seller
from tests.conftest import CUSTOMER, add

NEW_SELLER = {"id": "fifth-house", "name": "Fifth House", "tagline": "t", "description": "d", "origin": "Cebu",
              "founded": 2020, "accent": "#123456", "bottle": "dome"}


def new_product(pid, seller_id):
    return {"id": pid, "seller_id": seller_id, "name": "Extra", "price_centavos": 500000, "description": "d",
            "top_notes": ["a"], "heart_notes": ["b"], "base_notes": ["c"], "size_ml": 50, "family": "Floral",
            "concentration": "EDP", "stock": 5, "hue": "#ffffff"}


# ---- seed & limits ----

def test_seed_has_exactly_four_sellers_and_twenty_products(client, SessionTest):
    with SessionTest() as db:
        assert db.scalar(select(func.count(Seller.id))) == 4
        assert db.scalar(select(func.count(Product.id))) == 20
        counts = db.execute(select(Product.seller_id, func.count()).group_by(Product.seller_id)).all()
    assert sorted(c for _, c in counts) == [5, 5, 5, 5]
    assert all(s["product_count"] == 5 for s in client.get("/api/sellers").json())


def test_fifth_seller_rejected(client, monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", "secret")
    r = client.post("/api/admin/sellers", json=NEW_SELLER, headers={"X-Admin-Token": "secret"})
    assert r.status_code == 409 and "4 sellers" in r.json()["detail"]


def test_sixth_product_for_seller_rejected(client, monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", "secret")
    r = client.post("/api/admin/products", json=new_product("extra", "nordlys"), headers={"X-Admin-Token": "secret"})
    assert r.status_code == 409 and "at most 5" in r.json()["detail"]


def test_product_for_unknown_seller_rejected(client, monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", "secret")
    r = client.post("/api/admin/products", json=new_product("orphan", "nobody"), headers={"X-Admin-Token": "secret"})
    assert r.status_code == 404


def test_limits_enforced_at_service_level_after_deleting_one(SessionTest):
    from fastapi import HTTPException
    from app.schemas import ProductIn
    from app.services.catalog import create_product
    with SessionTest() as db:
        db.delete(db.get(Product, "nordlys-lingon"))
        db.commit()
        create_product(db, ProductIn(**new_product("nordlys-new", "nordlys")))  # back to 5: allowed
        db.commit()
        try:
            create_product(db, ProductIn(**new_product("nordlys-new2", "nordlys")))
            raise AssertionError("6th product accepted")
        except HTTPException as e:
            assert e.status_code == 409


def test_admin_endpoints_require_token(client):
    assert client.post("/api/admin/sellers", json=NEW_SELLER).status_code == 403


# ---- search, filter, sort ----

def test_search_by_name_and_brand(client):
    assert [p["id"] for p in client.get("/api/products", params={"q": "fjord"}).json()] == ["nordlys-fjord"]
    brand = client.get("/api/products", params={"q": "casa ylang"}).json()
    assert len(brand) == 5 and {p["seller_id"] for p in brand} == {"casa-ylang"}
    assert client.get("/api/products", params={"q": "zzz"}).json() == []


def test_filters_combine(client):
    r = client.get("/api/products", params={"seller": "velours-noir", "family": "Gourmand"}).json()
    assert {p["id"] for p in r} == {"velours-praline-noire", "velours-cafe-de-minuit"}
    r = client.get("/api/products", params={"min_price": 5000, "max_price": 7000}).json()
    assert r and all(500000 <= p["price_centavos"] <= 700000 for p in r)
    r = client.get("/api/products", params=[("family", "Fresh"), ("family", "Chypre")]).json()
    assert {p["family"] for p in r} == {"Fresh", "Chypre"}


def test_sorting(client):
    asc = [p["price_centavos"] for p in client.get("/api/products", params={"sort": "price_asc"}).json()]
    assert asc == sorted(asc) and len(asc) == 20
    desc = [p["price_centavos"] for p in client.get("/api/products", params={"sort": "price_desc"}).json()]
    assert desc == sorted(desc, reverse=True)
    names = [p["name"] for p in client.get("/api/products", params={"sort": "name_asc"}).json()]
    assert names == sorted(names)


def test_bad_filter_values_rejected(client):
    assert client.get("/api/products", params={"sort": "drop table"}).status_code == 422
    assert client.get("/api/products", params={"min_price": 9000, "max_price": 100}).status_code == 422


def test_product_detail_has_related_from_same_seller(client):
    r = client.get("/api/products/ylang-anao").json()
    assert r["product"]["seller"]["name"] == "Casa Ylang"
    assert len(r["related"]) == 4 and all(p["seller_id"] == "casa-ylang" for p in r["related"])
    assert client.get("/api/products/nope").status_code == 404


# ---- cart ----

def test_add_update_remove_and_totals(client, cart):
    add(client, cart, "ylang-anao", 2)          # 6,800 x2
    r = add(client, cart, "nordlys-fjord").json()  # 7,900
    assert r["item_count"] == 3
    assert r["subtotal_centavos"] == 2 * 680000 + 790000
    assert r["total_centavos"] == r["subtotal_centavos"] + 18000
    r = client.patch(f"/api/carts/{cart}/items/ylang-anao", json={"quantity": 1}).json()
    assert r["subtotal_centavos"] == 680000 + 790000
    r = client.delete(f"/api/carts/{cart}/items/nordlys-fjord").json()
    assert [i["product"]["id"] for i in r["items"]] == ["ylang-anao"]
    r = client.delete(f"/api/carts/{cart}/items/ylang-anao").json()
    assert r["items"] == [] and r["total_centavos"] == 0  # no shipping on an empty cart


def test_adding_same_product_twice_merges(client, cart):
    add(client, cart, "ylang-anao")
    r = add(client, cart, "ylang-anao").json()
    assert len(r["items"]) == 1 and r["items"][0]["quantity"] == 2


def test_cart_persists_across_requests(client, cart):
    add(client, cart, "velours-encre")
    # a "page refresh" is just a fresh GET with the id the browser kept in localStorage
    again = client.get(f"/api/carts/{cart}").json()
    assert again["items"][0]["product"]["id"] == "velours-encre"


def test_stock_limits(client, cart):
    assert add(client, cart, "atlas-medina-rose").status_code == 409  # stock 0
    assert add(client, cart, "velours-encre", 3).status_code == 409   # stock 2
    add(client, cart, "velours-encre", 2)
    assert add(client, cart, "velours-encre", 1).status_code == 409   # cumulative
    assert client.patch(f"/api/carts/{cart}/items/velours-encre", json={"quantity": 5}).status_code == 409


def test_invalid_quantities_rejected(client, cart):
    assert add(client, cart, "ylang-anao", 0).status_code == 422
    assert add(client, cart, "ylang-anao", -2).status_code == 422
    assert add(client, cart, "ylang-anao", 11).status_code == 422
    assert add(client, cart, "missing-product").status_code == 404
    assert client.get("/api/carts/not-a-cart").status_code == 404


# ---- checkout validation ----

def test_checkout_form_validation(client, cart):
    add(client, cart, "ylang-anao")
    base = {"cart_id": cart, "payment_method": "gcash"}
    for bad in ({"email": "not-an-email"}, {"phone": "12345"}, {"name": " "}, {"address": "short"}):
        r = client.post("/api/checkout", json={**base, "customer": {**CUSTOMER, **bad}})
        assert r.status_code == 422, bad
    r = client.post("/api/checkout", json={**base, "payment_method": "bitcoin", "customer": CUSTOMER})
    assert r.status_code == 422


def test_checkout_empty_cart_rejected(client, cart):
    r = client.post("/api/checkout", json={"cart_id": cart, "customer": CUSTOMER, "payment_method": "card"})
    assert r.status_code == 422 and "empty" in r.json()["detail"]


def test_client_cannot_override_price(client, cart):
    add(client, cart, "ylang-anao")
    body = {"cart_id": cart, "customer": CUSTOMER, "payment_method": "card", "total_centavos": 1, "price": 1}
    order = client.post("/api/checkout", json=body).json()["order"]
    assert order["total_centavos"] == 680000 + 18000


def test_newsletter_signup(client):
    assert client.post("/api/newsletter", json={"email": "a@example.com"}).json() == {"subscribed": True, "already": False}
    assert client.post("/api/newsletter", json={"email": "A@example.com"}).json()["already"] is True
    assert client.post("/api/newsletter", json={"email": "nope"}).status_code == 422
