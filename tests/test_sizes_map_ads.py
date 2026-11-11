"""Sizes, the homepage map ad, and the homepage ads telling the truth."""
import re

from velora.extensions import db
from velora.models import CartItem, DiscountCode, Order, OrderItem, Product, ProductReview, StoreSetting, utcnow

from .conftest import default_address, get_user, in_stock_product, login, sized_product


def _checkout(client):
    page = client.get("/checkout").get_data(as_text=True)
    token = re.search(r'checkout_token[^>]*value="([^"]+)"', page).group(1)
    addr = default_address(get_user("buyer1@velora.example"))
    return client.post("/checkout", data={"checkout_token": token, "address_choice": str(addr.id)})


# ------------------------------------------------------------------- sizes

def test_sized_products_show_size_buttons_and_others_do_not(client):
    dress = Product.query.filter_by(slug="linen-wrap-midi-dress").one()
    html = client.get(f"/shop/p/{dress.slug}").get_data(as_text=True)
    assert 'data-size-picker' in html and html.count('name="size"') == len(dress.size_list) == 5
    tote = Product.query.filter_by(slug="structured-leather-tote").one()
    assert "data-size-picker" not in client.get(f"/shop/p/{tote.slug}").get_data(as_text=True)


def test_clothes_shoes_and_rings_have_the_right_sizes(app):
    get = lambda slug: Product.query.filter_by(slug=slug).one().size_list
    assert get("linen-wrap-midi-dress") == ["XS", "S", "M", "L", "XL"]
    assert get("red-runner-sneakers") == [str(n) for n in range(39, 47)]
    assert get("18k-gold-stacking-rings-set-of-3") == ["5", "6", "7", "8", "9"]
    assert Product.query.filter_by(slug="structured-leather-tote").one().size_list == []
    assert Product.query.filter_by(slug="minimalist-leather-strap-watch").one().size_list == []


def test_size_is_required_to_add_a_sized_product(client):
    p = sized_product()
    r = client.post(f"/cart/add/{p.id}", data={"quantity": 1}, headers={"X-Requested-With": "fetch"})
    assert r.status_code == 409 and "choose a size" in r.json["error"].lower()
    r = client.post(f"/cart/add/{p.id}", data={"quantity": 1, "size": "XXXL"}, headers={"X-Requested-With": "fetch"})
    assert r.status_code == 409
    r = client.post(f"/cart/add/{p.id}", data={"quantity": 1, "size": p.size_list[0]}, headers={"X-Requested-With": "fetch"})
    assert r.json["ok"] and r.json["count"] == 1 and f"Size {p.size_list[0]}" in r.json["drawer"]


def test_unsized_products_ignore_a_size_value(client):
    p = in_stock_product()
    r = client.post(f"/cart/add/{p.id}", data={"quantity": 1, "size": "L"}, headers={"X-Requested-With": "fetch"})
    assert r.json["ok"] and "Size L" not in r.json["drawer"]


def test_same_product_in_two_sizes_is_two_lines_sharing_stock(client):
    p = sized_product()
    a, b = p.size_list[0], p.size_list[1]
    client.post(f"/cart/add/{p.id}", data={"quantity": 2, "size": a})
    client.post(f"/cart/add/{p.id}", data={"quantity": 1, "size": b})
    html = client.get("/cart").get_data(as_text=True)
    assert f"Size {a}" in html and f"Size {b}" in html
    assert client.get("/cart/drawer").json["count"] == 3
    # update / remove only touch the chosen size
    client.post(f"/cart/update/{p.id}", data={"quantity": 5, "size": a}, headers={"X-Requested-With": "fetch"})
    assert client.get("/cart/drawer").json["count"] == 6
    client.post(f"/cart/remove/{p.id}", data={"size": a})
    assert client.get("/cart/drawer").json["count"] == 1
    # stock is shared by all sizes: cannot add more than the product has in total
    p.stock = 3
    db.session.commit()
    client.post(f"/cart/add/{p.id}", data={"quantity": 20, "size": a})
    assert client.get("/cart/drawer").json["count"] <= 3


def test_guest_sized_cart_merges_into_the_account(client):
    p = sized_product()
    client.post(f"/cart/add/{p.id}", data={"quantity": 2, "size": p.size_list[2]})
    login(client, "buyer1@velora.example", "Buyer123!")
    u = get_user("buyer1@velora.example")
    item = CartItem.query.join(CartItem.cart).filter_by(user_id=u.id).one()
    assert item.size == p.size_list[2] and item.quantity == 2


def test_size_is_saved_on_the_order_and_shown_everywhere(customer):
    p = sized_product()
    size = p.size_list[1]
    customer.post(f"/cart/add/{p.id}", data={"quantity": 1, "size": size})
    assert f"Size {size}" in customer.get("/checkout").get_data(as_text=True)
    r = _checkout(customer)
    assert r.status_code == 302
    o = Order.query.order_by(Order.id.desc()).first()
    assert OrderItem.query.filter_by(order_id=o.id).one().size == size
    assert f"Size {size}" in customer.get(r.headers["Location"]).get_data(as_text=True)
    assert f"Size {size}" in customer.get(f"/account/orders/{o.number}").get_data(as_text=True)
    customer.post("/account/switch-profile")
    assert f"Size {size}" in customer.get(f"/seller/orders/{o.number}").get_data(as_text=True)
    assert f"({size})" in customer.get("/seller/export/orders.csv").get_data(as_text=True)


def test_product_cards_send_sized_items_to_the_product_page(client):
    html = client.get("/shop/c/women").get_data(as_text=True)
    assert "Choose size" in html
    html = client.get("/shop/c/bags").get_data(as_text=True)
    assert "Choose size" not in html and "Add to bag" in html


def test_seller_can_edit_sizes(seller):
    p = Product.query.filter_by(slug="heavyweight-white-tee").one()
    data = {"name": p.name, "brand": p.brand, "category_id": p.category_id, "short_description": "x", "description": "y",
            "price": "790", "stock": "10", "status": "active", "sizes": "S, M ,L"}
    assert seller.post(f"/seller/products/{p.id}", data=data).status_code == 302
    db.session.expire_all()
    assert Product.query.get(p.id).size_list == ["S", "M", "L"]
    bad = seller.post(f"/seller/products/{p.id}", data={**data, "sizes": "S,S"})
    assert bad.status_code == 200 and "field__error" in bad.get_data(as_text=True)


# --------------------------------------------------------------------- map

def test_homepage_has_the_map_ad_with_local_leaflet_only(client):
    html = client.get("/").get_data(as_text=True)
    assert 'id="store-map"' in html and "Try it on in store" in html
    assert "Get directions" in html and "openstreetmap.org/directions" in html
    scripts = re.findall(r'<script[^>]+src="([^"]+)"', html)
    assert all(s.startswith("/static/") for s in scripts), scripts  # nothing loaded from a CDN
    for path in ("/static/vendor/leaflet/leaflet.js", "/static/vendor/leaflet/leaflet.css",
                 "/static/vendor/leaflet/images/marker-icon.png", "/static/js/store-map.js"):
        assert client.get(path).status_code == 200, path
    assert "script-src 'self'" in client.get("/").headers["Content-Security-Policy"]


def test_admin_changes_the_map_location(admin):
    data = {"shipping_flat": "150", "free_shipping_threshold": "2500", "low_stock_threshold": "8",
            "store_announcement": "", "support_email": "care@example.com", "store_name": "Velora Makati",
            "store_address": "1 Ayala Avenue, Makati", "store_hours": "Daily 10-8", "store_lat": "14.5547", "store_lng": "121.0244"}
    assert admin.post("/admin/settings", data=data).status_code == 302
    html = admin.get("/").get_data(as_text=True)
    assert "Velora Makati" in html and 'data-lat="14.5547"' in html and 'data-lng="121.0244"' in html
    assert "1 Ayala Avenue, Makati" in admin.get("/pages/contact").get_data(as_text=True)


def test_invalid_map_coordinates_are_rejected(admin):
    data = {"shipping_flat": "150", "free_shipping_threshold": "2500", "low_stock_threshold": "8", "store_announcement": "",
            "support_email": "care@example.com", "store_name": "X", "store_address": "Y", "store_hours": "Z",
            "store_lat": "999", "store_lng": "abc"}
    r = admin.post("/admin/settings", data=data)
    assert r.status_code == 200 and "Latitude" in r.get_data(as_text=True) and "Longitude" in r.get_data(as_text=True)
    db.session.expire_all()
    assert db.session.get(StoreSetting, "store_lat").value == "14.5507"  # unchanged


def test_map_popup_text_cannot_inject_markup(admin):
    data = {"shipping_flat": "150", "free_shipping_threshold": "2500", "low_stock_threshold": "8", "store_announcement": "",
            "support_email": "care@example.com", "store_name": "<script>alert(1)</script>", "store_address": "A", "store_hours": "B",
            "store_lat": "14.5", "store_lng": "121.0"}
    admin.post("/admin/settings", data=data)
    html = admin.get("/").get_data(as_text=True)
    assert "<script>alert(1)</script>" not in html and "&lt;script&gt;alert(1)&lt;/script&gt;" in html


# -------------------------------------------------------- honest homepage ads

def test_hero_ad_features_clothing_and_a_real_rating(client):
    html = client.get("/").get_data(as_text=True)
    slug = re.search(r'class="hero__card" href="/shop/p/([a-z0-9-]+)"', html).group(1)
    hero = Product.query.filter_by(slug=slug).one()
    assert hero.category.slug in ("women", "men"), hero.name  # clothing, next to a model photo
    avg = db.session.query(db.func.avg(ProductReview.rating)).filter(ProductReview.is_hidden.is_(False)).scalar()
    assert f"{round(float(avg), 1)} / 5" in html  # the real average, not a made-up number


def test_sale_banner_only_runs_while_the_code_works(client):
    html = client.get("/").get_data(as_text=True)
    assert "SEASON15 · 15% off" in html and "Ends " in html and "3 weeks" not in html
    d = DiscountCode.query.filter_by(code="SEASON15").one()
    d.is_active = False
    db.session.commit()
    html = client.get("/").get_data(as_text=True)
    assert "SEASON15" not in html and "The new" in html  # falls back to a plain collection banner
    d.is_active, d.ends_at = True, utcnow().replace(year=2020)
    db.session.commit()
    assert "SEASON15" not in client.get("/").get_data(as_text=True)


def test_no_ad_or_page_mentions_cars_anymore(client):
    for url in ("/", "/shop/", "/pages/about", "/pages/shipping", "/pages/returns", "/pages/faq", "/pages/contact"):
        html = client.get(url).get_data(as_text=True).lower()
        assert not re.search(r"\bcars?\b", html), url
        assert "showroom" not in html and "test drive" not in html, url


def test_image_fallback_rule_leaves_map_tiles_alone(client):
    """Regression: the 'broken image -> placeholder' rule once replaced map tiles with bag placeholders."""
    js = client.get("/static/js/app.js").get_data(as_text=True)
    assert '!img.closest(".leaflet-container")' in js
