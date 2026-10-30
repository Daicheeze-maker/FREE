from velora.extensions import db
from velora.models import CartItem, Product, ProductReview

from .conftest import get_user, in_stock_product, login


def test_home_and_catalog_render(client):
    assert client.get("/").status_code == 200
    r = client.get("/shop/")
    assert r.status_code == 200 and "product" in r.get_data(as_text=True)


def test_search_matches_name_and_category(client):
    html = client.get("/shop/?q=matcha").get_data(as_text=True)
    assert "Ceremonial Grade Matcha" in html
    html = client.get("/shop/?q=bakery").get_data(as_text=True)  # category name
    assert "Country Sourdough Loaf" in html


def test_search_empty_state(client):
    html = client.get("/shop/?q=zzzznotathing").get_data(as_text=True)
    assert "Nothing matches" in html


def test_filters_and_sorting(client):
    html = client.get("/shop/?sort=price_asc&max=300").get_data(as_text=True)
    assert "Cold-Pressed Extra Virgin Olive Oil" not in html  # ₱980
    assert "72% Davao Dark Chocolate" in html
    html = client.get("/shop/?availability=in_stock").get_data(as_text=True)
    assert "Sea Salt Rosemary Almonds" not in html  # stock 0
    html = client.get("/shop/?brand=Casa+Oliva").get_data(as_text=True)
    assert "Olive Oil" in html and "Matcha" not in html


def test_category_page_and_ajax_partial(client):
    r = client.get("/shop/c/pantry", headers={"X-Requested-With": "fetch"})
    assert r.status_code == 200 and "<html" not in r.get_data(as_text=True)
    assert client.get("/shop/c/no-such-aisle").status_code == 404


def test_pagination(client):
    assert "pager" in client.get("/shop/").get_data(as_text=True)  # 24 products, 12 per page
    assert client.get("/shop/?page=2").status_code == 200


def test_archived_product_hidden(client):
    p = in_stock_product()
    p.status = "archived"
    db.session.commit()
    assert client.get(f"/shop/p/{p.slug}").status_code == 404
    assert p.name not in client.get("/shop/").get_data(as_text=True)


def test_guest_session_cart_add_update_remove(client):
    p = in_stock_product()
    r = client.post(f"/cart/add/{p.id}", data={"quantity": 2}, headers={"X-Requested-With": "fetch"})
    assert r.json["ok"] and r.json["count"] == 2
    r = client.post(f"/cart/update/{p.id}", data={"quantity": 5}, headers={"X-Requested-With": "fetch"})
    assert r.json["count"] == 5
    r = client.post(f"/cart/update/{p.id}", data={"quantity": 9999}, headers={"X-Requested-With": "fetch"})
    assert r.json["count"] == min(p.stock, 20)  # clamped
    r = client.post(f"/cart/remove/{p.id}", headers={"X-Requested-With": "fetch"})
    assert r.json["count"] == 0


def test_cannot_add_sold_out(client):
    p = Product.query.filter_by(stock=0).first()
    r = client.post(f"/cart/add/{p.id}", headers={"X-Requested-With": "fetch"})
    assert r.status_code == 409 and not r.json["ok"]


def test_guest_cart_merges_on_login(client):
    p = in_stock_product()
    client.post(f"/cart/add/{p.id}", data={"quantity": 3})
    login(client, "customer@velora.example", "Customer123!")
    u = get_user("customer@velora.example")
    item = CartItem.query.join(CartItem.cart).filter_by(user_id=u.id).filter(CartItem.product_id == p.id).first()
    assert item and item.quantity == 3
    assert "Your bag" in client.get("/cart").get_data(as_text=True)


def test_customer_cart_is_persistent(app):
    p = in_stock_product()
    c1 = app.test_client()
    login(c1, "customer@velora.example", "Customer123!")
    c1.post(f"/cart/add/{p.id}", data={"quantity": 1})
    c2 = app.test_client()
    login(c2, "customer@velora.example", "Customer123!")
    assert p.name in c2.get("/cart").get_data(as_text=True)


def test_wishlist_toggle(customer):
    p = Product.query.filter_by(name="Bronze-Cut Rigatoni").first()
    r = customer.post(f"/account/wishlist/{p.id}", headers={"X-Requested-With": "fetch"})
    assert r.json["saved"] is True
    r = customer.post(f"/account/wishlist/{p.id}", headers={"X-Requested-With": "fetch"})
    assert r.json["saved"] is False


def test_wishlist_requires_login(client):
    r = client.post("/account/wishlist/1", headers={"X-Requested-With": "fetch"})
    assert r.status_code == 401


def test_recently_viewed(client):
    p = in_stock_product()
    client.get(f"/shop/p/{p.slug}")
    assert "Recently viewed" in client.get("/").get_data(as_text=True)


def test_newsletter_validation_and_persistence(client):
    r = client.post("/newsletter", data={"email": "nope"}, headers={"X-Requested-With": "fetch"})
    assert r.status_code == 400
    r = client.post("/newsletter", data={"email": "fan@example.com"}, headers={"X-Requested-With": "fetch"})
    assert r.json["ok"]
    r = client.post("/newsletter", data={"email": "fan@example.com"}, headers={"X-Requested-With": "fetch"})
    assert "already" in r.json["message"]


# ------------------------------------------------------------------ reviews

def _delivered_unreviewed_product(user):
    from velora.models import Order, OrderStatus
    reviewed = {r.product_id for r in ProductReview.query.filter_by(user_id=user.id)}
    for o in Order.query.filter_by(user_id=user.id, status=OrderStatus.DELIVERED):
        for it in o.items:
            if it.product_id not in reviewed:
                return it.product
    return None


def test_review_requires_purchase(customer):
    u = get_user("customer@velora.example")
    from velora.models import Order, OrderItem
    bought = {i.product_id for i in OrderItem.query.join(Order).filter(Order.user_id == u.id)}
    p = Product.query.filter(~Product.id.in_(bought), Product.status == "active").first()
    customer.post(f"/shop/p/{p.slug}/review", data={"rating": "5", "title": "Great stuff", "body": "Never bought it but love it"})
    assert ProductReview.query.filter_by(user_id=u.id, product_id=p.id).count() == 0


def test_review_after_delivery_and_duplicate_blocked(customer):
    u = get_user("customer@velora.example")
    p = _delivered_unreviewed_product(u)
    assert p is not None
    data = {"rating": "4", "title": "Really good", "body": "Arrived fresh and tasted wonderful."}
    customer.post(f"/shop/p/{p.slug}/review", data=data)
    customer.post(f"/shop/p/{p.slug}/review", data=data)
    assert ProductReview.query.filter_by(user_id=u.id, product_id=p.id).count() == 1


def test_review_invalid_rating_rejected(customer):
    u = get_user("customer@velora.example")
    p = _delivered_unreviewed_product(u)
    customer.post(f"/shop/p/{p.slug}/review", data={"rating": "9", "title": "Hmm hmm", "body": "Ten out of five."})
    assert ProductReview.query.filter_by(user_id=u.id, product_id=p.id).count() == 0
