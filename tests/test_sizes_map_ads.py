"""The homepage map ad, and the homepage ads telling the truth."""
import re

from velora.extensions import db
from velora.models import CartItem, DiscountCode, Order, OrderItem, Product, ProductReview, StoreSetting, utcnow

from .conftest import default_address, get_user, in_stock_product, login, sized_product


def _checkout(client):
    page = client.get("/checkout").get_data(as_text=True)
    token = re.search(r'checkout_token[^>]*value="([^"]+)"', page).group(1)
    addr = default_address(get_user("buyer1@velora.example"))
    return client.post("/checkout", data={"checkout_token": token, "address_choice": str(addr.id)})


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

def test_hero_ad_features_a_watch_and_a_real_rating(client):
    html = client.get("/").get_data(as_text=True)
    slug = re.search(r'class="hero__card" href="/shop/p/([a-z0-9-]+)"', html).group(1)
    assert Product.query.filter_by(slug=slug).one().is_featured
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
    assert 'img.closest(".leaflet-container")' in js
