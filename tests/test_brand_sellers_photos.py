"""Brand name, seller sign-up, admin's active-sellers page, back buttons and automatic product photos."""
import re
from unittest.mock import patch

import pytest
import requests

from velora.cli import remove_demo_accounts
from velora.extensions import db
from velora.models import Product, ProductImage, User

from .conftest import get_user, login


def register(client, email, kind=None, name="Sam Seller"):
    data = {"full_name": name, "email": email, "password": "Secret123", "confirm": "Secret123", "accept": "y"}
    if kind:
        data["account_type"] = kind
    return client.post("/account/register", data=data)


# ---------------------------------------------------------------- brand

def test_store_has_its_own_name_everywhere(client):
    for url in ("/", "/account/login", "/shop/", "/pages/about"):
        page = client.get(url).get_data(as_text=True)
        assert "Velora" not in page and "velora." not in page.replace("velora.example", ""), url
        assert "aurelune" in page.lower(), url
    assert "<title>Sign in · Aurelune</title>" in client.get("/account/login").get_data(as_text=True)


def test_brand_name_can_be_changed_from_the_environment(tmp_path):
    from velora import create_app
    app = create_app("testing", SQLALCHEMY_DATABASE_URI=f"sqlite:///{tmp_path / 'b.db'}", BRAND_NAME="Maison Test")
    with app.app_context():
        db.create_all()
        page = app.test_client().get("/account/login").get_data(as_text=True)
    assert "Maison Test" in page and "maison test" in page.lower()


# ---------------------------------------------------------------- seller sign-up

def test_registering_as_a_seller_opens_seller_studio(client):
    r = register(client, "shop@example.com", "seller")
    assert r.status_code == 302 and r.headers["Location"].endswith("/seller/")
    db.session.expire_all()
    assert get_user("shop@example.com#seller") is not None and get_user("shop@example.com").role == "customer"
    assert get_user("shop@example.com#seller").last_login_at is not None
    assert client.get("/seller/").status_code == 200
    assert client.get("/account/").status_code == 403  # in the seller profile; one click to the buyer profile
    assert client.post("/account/switch-profile").status_code == 302
    assert client.get("/account/").status_code == 200


def test_registering_as_a_buyer_goes_to_the_account(client):
    for kind in ("buyer", None):
        c = client.application.test_client()
        r = register(c, f"{kind}@example.com", kind)
        assert r.headers["Location"].endswith("/account/")


def test_register_page_offers_both_choices(client):
    page = client.get("/account/register").get_data(as_text=True)
    assert 'name="account_type" value="buyer"' in page and 'name="account_type" value="seller"' in page


def test_bad_account_type_is_rejected(client):
    r = register(client, "x@example.com", "admin")
    assert r.status_code == 200 and get_user("x@example.com") is None


# ---------------------------------------------------------------- admin sees active sellers

def test_admin_sees_active_sellers(app, admin, client):
    other = app.test_client()
    register(other, "newshop@example.com", "seller", "New Shop")
    page = admin.get("/admin/sellers").get_data(as_text=True)
    assert "newshop@example.com#seller" in page and "New Shop" in page and "Active" in page
    assert "newshop@example.com</a>" in page  # the owner (buyer profile) is shown
    dash = admin.get("/admin/").get_data(as_text=True)
    assert "Active sellers" in dash and 'href="/admin/sellers"' in dash
    assert 'href="/admin/sellers"' in dash.split("sidebar__nav")[1]  # in the sidebar too


def test_inactive_and_disabled_sellers_are_marked(app, admin):
    from datetime import timedelta
    from velora.models import utcnow
    s = get_user("buyer1@velora.example#seller")
    s.last_login_at = utcnow() - timedelta(days=90)
    get_user("buyer2@velora.example#seller").is_active_account = False
    db.session.commit()
    page = admin.get("/admin/sellers").get_data(as_text=True)
    assert "Not active lately" in page and "Disabled" in page


def test_only_admins_can_see_the_sellers_page(customer, client):
    assert customer.get("/admin/sellers").status_code in (302, 403)


# ---------------------------------------------------------------- back buttons

@pytest.mark.parametrize("url", ["/shop/", "/shop/c/accessories", "/shop/p/linen-wrap-midi-dress", "/cart", "/pages/about"])
def test_pages_have_a_back_button(client, url):
    assert "data-back" in client.get(url).get_data(as_text=True), url


def test_home_has_no_back_button(client):
    assert "backrow" not in client.get("/").get_data(as_text=True)


def test_console_pages_have_a_back_button(seller, admin):
    assert "data-back" in seller.get("/seller/products").get_data(as_text=True)
    assert "backrow" not in seller.get("/seller/").get_data(as_text=True)


# ---------------------------------------------------------------- automatic photos

class Resp:
    def __init__(self, status=200, data=None, content=b""):
        self.status_code, self._d, self.content = status, data, content

    def json(self):
        return self._d

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(str(self.status_code))

    def iter_content(self, n):
        for i in range(0, len(self.content), n):
            yield self.content[i:i + n]


def _jpeg():
    import io
    from PIL import Image
    b = io.BytesIO()
    Image.new("RGB", (80, 120), (120, 80, 40)).save(b, "JPEG")
    return b.getvalue()


def fake_openverse():
    n = {"i": 0}

    def get(url, **kw):
        if "/thumb/" in url:
            return Resp(content=_jpeg())
        if url.endswith("/v1/images/"):
            n["i"] += 1
            i = n["i"]
            return Resp(data={"result_count": 1, "results": [{
                "id": f"{i:08d}-aaaa-bbbb-cccc-{i:012d}", "title": f"Shoe {i}", "creator": "Jo", "license": "by", "license_version": "2.0",
                "width": 400, "height": 600, "foreign_landing_url": "https://example.org/x"}]})
        return Resp(404, {})
    return patch("velora.services.openverse.requests.get", side_effect=get), n


def test_fill_photos_works_without_any_key(app):
    from velora.services import photo_fill
    ProductImage.query.filter(ProductImage.product_id.in_(
        [p.id for p in Product.query.filter(Product.slug.in_(["minimalist-leather-strap-watch", "smart-fitness-watch"]))])).delete(synchronize_session=False)
    db.session.commit()
    p, calls = fake_openverse()
    with p, patch("velora.services.photo_check.check_remote", return_value={}):
        res = photo_fill.fill_products(limit=50)
    assert res.source == "Openverse" and "Minimalist Leather Strap Watch" in res.done
    db.session.expire_all()
    shoe = Product.query.filter_by(slug="minimalist-leather-strap-watch").one()
    assert shoe.primary_image.filename.endswith(".webp") and "Openverse" in shoe.primary_image.credit and "CC BY 2.0" in shoe.primary_image.credit


def test_fill_photos_command_never_breaks_start_up_when_offline(app):
    with patch("velora.services.openverse.requests.get", side_effect=requests.ConnectionError("offline")), \
            patch("velora.services.photo_check.check_remote", return_value={}):
        out = app.test_cli_runner().invoke(args=["fill-photos"])
    assert out.exit_code == 0 and "no internet" in out.output


def test_openverse_only_downloads_from_its_own_host(app):
    from velora.services import openverse, pexels
    photo = pexels.PexelsPhoto(id="x", alt="a", photographer="b", page_url="", thumb="https://evil.example/x.jpg",
                               image="https://evil.example/x.jpg", width=1, height=1)
    with pytest.raises(pexels.PexelsError):
        openverse.download(photo)


# ---------------------------------------------------------------- every product has a picture

def test_every_product_has_a_photo_in_a_fresh_store(client):
    missing = [p.name for p in Product.query.all() if not p.images]
    assert missing == []
    for p in Product.query.all():
        assert p.primary_image.url.startswith("https://images.unsplash.com/photo-"), p.name


def test_collection_pages_render_a_photo_for_every_card(client):
    for slug in ("dress-watches", "dive-watches", "chronographs", "field-pilot", "smart-watches", "ladies-watches"):
        page = client.get(f"/shop/c/{slug}").get_data(as_text=True)
        cards = page.count('class="pcard"')
        assert cards >= 3 and page.count("images.unsplash.com/photo-") >= cards, slug


def test_photo_less_watches_get_a_photo_on_refresh_without_touching_others(app):
    from velora.seed import refresh_catalog
    watch = Product.query.filter_by(slug="moonphase-automatic-dress-watch").one()
    keep = Product.query.filter_by(slug="smart-fitness-watch").one()
    ProductImage.query.filter_by(product_id=watch.id).delete()
    before = [i.url for i in keep.images]
    db.session.commit()
    changes = refresh_catalog()
    db.session.expire_all()
    assert "added a photo to Moonphase Automatic Dress Watch" in changes
    assert Product.query.filter_by(slug="moonphase-automatic-dress-watch").one().images
    assert [i.url for i in Product.query.filter_by(slug="smart-fitness-watch").one().images] == before


def test_page_carries_the_photo_fallback_chain_for_the_browser(client):
    import html as h, json
    page = client.get("/").get_data(as_text=True)
    raw = re.search(r'data-photo-alts="([^"]*)"', page).group(1)
    chain = json.loads(h.unescape(raw))
    assert chain["1508685096489-7aacd43bd3b1"].startswith("https://images.unsplash.com/photo-1524805444758")
    # every chain ends on a photo that is known to load, and every watch has somewhere to go if its first photo is gone
    from velora.seed import PRODUCTS
    for row in PRODUCTS:
        ids = row[10]
        assert ids[-1] in ("1523275335684-37898b6baf30", "1522312346375-d1a52e2b99b3", "1524592094714-0f0654e20314",
                           "1547996160-81dfa63595aa", "1434056886845-dac89ffe9b56"), row[0]


def test_static_scripts_are_versioned_so_browsers_never_keep_old_ones(client):
    page = client.get("/").get_data(as_text=True)
    assert re.search(r'js/app\.js\?v=\d+', page) and re.search(r'css/app\.css\?v=\d+', page)


def test_pin_map_has_browser_fallbacks_and_csp_allows_them(client):
    js = client.get("/static/js/pin-map.js").get_data(as_text=True)
    assert "nominatim.openstreetmap.org" in js and "bigdatacloud" in js
    csp = client.get("/").headers["Content-Security-Policy"]
    assert "https://nominatim.openstreetmap.org" in csp and "script-src 'self'" in csp
