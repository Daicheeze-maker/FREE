"""Every product in the right collection, a safe refresh for older databases, and filling missing photos."""
import re
from unittest.mock import patch

import requests

import pytest

from velora import create_app
from velora.cli import demo_status, init_database
from velora.extensions import db
from velora.models import Category, Order, Product, ProductImage, StoreSetting, User
from velora.seed import refresh_catalog, seed

from .test_pexels_photos import KEY, fake_pexels, jpeg, page, photo  # noqa: F401


# ------------------------------------------------------------- right collections

def names(slug):
    return sorted(p.name for p in Category.query.filter_by(slug=slug).one().products)


def test_collections_and_their_order(app):
    ordered = [c.name for c in Category.query.order_by(Category.position)]
    assert ordered == ["Dress Watches", "Dive Watches", "Chronographs", "Field & Pilot", "Smart Watches", "Ladies Watches"]
    assert [len(names(c.slug)) for c in Category.query.order_by(Category.position)] == [14, 13, 14, 13, 13, 13]


def test_every_watch_has_size_colour_and_a_photo(app):
    for p in Product.query.all():
        assert p.size_list and p.color_list, p.name
        assert p.images and p.primary_image.url.startswith(("https://images.unsplash.com/photo-", "/static/img/watches/")), p.name
        assert p.engraving_fee_minor is None or p.engraving_fee_minor >= 0
    assert Product.query.filter(Product.engraving_fee_minor.isnot(None)).count() >= 15
    assert Product.query.filter_by(slug="smart-gps-sport-watch").one().offers_engraving is False


def blank_demo_photos():
    """Take away the photos of the first nine watches (what a store looks like before its photos are filled in)."""
    ids = [p.id for p in Product.query.order_by(Product.id).limit(9)]
    ProductImage.query.filter(ProductImage.product_id.in_(ids)).delete(synchronize_session=False)
    db.session.commit()
    db.session.expire_all()


def test_menu_shows_the_watch_collections(client):
    html = client.get("/").get_data(as_text=True)
    nav = html.split("header__nav")[1].split("</nav>")[0]
    for name in ("Dress Watches", "Dive Watches", "Chronographs", "Smart Watches", "Ladies Watches"):
        assert name in nav
    for slug in ("dress-watches", "dive-watches", "chronographs", "field-pilot", "smart-watches", "ladies-watches"):
        assert client.get(f"/shop/c/{slug}").status_code == 200


# --------------------------------------------- an older (fashion) store becomes the watch store

def _fashion_store(app):
    """Put the database back the way the fashion releases left it: other collections, a loose watch, orders on them."""
    from velora.models import Cart, CartItem, OrderItem, WishlistItem
    seed(demo_accounts=True)
    watch = Product.query.filter_by(slug="diver-automatic-200m").one()
    old_watches = Category(name="Watches", slug="watches", icon="watch", description="x", position=0)
    women = Category(name="Women", slug="women", icon="shirt", description="x", position=1)
    db.session.add_all([old_watches, women])
    db.session.flush()
    watch.category = old_watches
    watch.sizes = watch.colors = watch.engraving_fee_minor = None  # no options yet
    dress = Product(name="Linen Wrap Midi Dress", slug="linen-wrap-midi-dress", sku="OLD-1", brand="Old", category=women,
                    price_minor=249000, stock=5, short_description="x", description="x")
    own = Product(name="My Own Watch", slug="my-own-watch", sku="OLD-2", brand="Me", category=old_watches,
                  price_minor=500000, stock=3, short_description="x", description="x")
    db.session.add_all([dress, own])
    db.session.flush()
    buyer = User(email="real@example.com", full_name="Real Buyer", role="customer")
    buyer.set_password("Secret123")
    db.session.add(buyer)
    db.session.flush()
    cart = Cart(user_id=buyer.id)
    db.session.add(cart)
    db.session.flush()
    db.session.add(CartItem(cart_id=cart.id, product_id=dress.id, quantity=1, size="M"))
    db.session.add(WishlistItem(user_id=buyer.id, product_id=dress.id))
    order = Order(number="VM-REAL-1", user_id=buyer.id, checkout_token="real-token", ship_name="x", ship_phone="1",
                  ship_address="y", subtotal_minor=249000, total_minor=249000)
    db.session.add(order)
    from velora.models import OrderItem as OI
    order.items.append(OI(product_id=dress.id, product_name=dress.name, product_sku="OLD-1", product_brand="Old",
                          unit_price_minor=249000, quantity=1, line_total_minor=249000, size="M"))
    db.session.commit()
    return order.number


def test_a_fashion_store_becomes_the_watch_store_and_keeps_orders(tmp_path):
    from velora.models import CartItem, OrderItem, WishlistItem
    app = create_app("testing", SQLALCHEMY_DATABASE_URI=f"sqlite:///{tmp_path / 'old.db'}")
    with app.app_context():
        init_database()
        number = _fashion_store(app)
        db.session.add(StoreSetting(key="photo_hero", value="mine.webp"))  # work the user already did
        db.session.commit()
        assert demo_status() == "stale"
    out = app.test_cli_runner().invoke(args=["upgrade-demo"]).output  # no prompt, nothing to confirm
    assert "removed 1 product(s) the store no longer sells" in out and "removed the empty Women collection" in out
    with app.app_context():
        assert demo_status() == "current"
        assert Product.query.filter_by(slug="linen-wrap-midi-dress").first() is None
        assert [c.slug for c in Category.query.order_by(Category.position)] == [
            "dress-watches", "dive-watches", "chronographs", "field-pilot", "smart-watches", "ladies-watches"]
        assert User.query.filter_by(email="real@example.com").count() == 1  # real accounts and their orders are untouched
        assert Order.query.filter_by(number="VM-REAL-1").count() == 1
        assert User.query.filter_by(email="buyer1@velora.example").count() == 0  # the old sample accounts are cleaned away
        old_line = OrderItem.query.filter_by(product_sku="OLD-1").one()
        assert old_line.product_id is None and old_line.product_name == "Linen Wrap Midi Dress" and old_line.size == "M"
        assert Order.query.filter_by(number=number).one() is not None
        assert CartItem.query.filter_by(size="M").count() == 0 and WishlistItem.query.filter(
            WishlistItem.product_id.notin_([p.id for p in Product.query])).count() == 0
        assert db.session.get(StoreSetting, "photo_hero").value == "mine.webp"
        diver = Product.query.filter_by(slug="diver-automatic-200m").one()
        assert diver.category.slug == "dive-watches" and diver.size_list == ["40 mm", "42 mm", "44 mm"] and diver.offers_engraving
        own = Product.query.filter_by(slug="my-own-watch").one()
        assert own.category.slug == "dress-watches"  # a watch the seller added is kept
    again = app.test_cli_runner().invoke(args=["upgrade-demo"]).output
    assert "Catalog updated" not in again  # the second start changes nothing


def test_refresh_never_changes_a_catalog_that_is_already_right(app):
    assert demo_status() == "current"
    assert refresh_catalog() == []


def test_refresh_keeps_a_seller_s_own_edits(app):
    watch = Product.query.filter_by(slug="chronograph-steel-watch").one()
    watch.price_minor, watch.sizes = 123_400, "41 mm"  # the seller changed a price and the sizes
    db.session.commit()
    refresh_catalog()
    watch = Product.query.filter_by(slug="chronograph-steel-watch").one()
    assert watch.price_minor == 123_400 and watch.size_list == ["41 mm"]


# ------------------------------------------------------ fill missing & broken photos

def _working_remote(*urls):
    """Pretend only these remote photo links load."""
    return lambda url, timeout=6, user_agent=None: url in urls


@pytest.fixture()
def keyed(app):
    app.config["PEXELS_API_KEY"] = KEY
    return app


def test_fill_gives_photos_to_missing_and_broken_ones_and_leaves_working_ones(seller, keyed):
    blank_demo_photos()
    tote = Product.query.filter_by(slug="smart-fitness-watch").one()
    tote_url = tote.images[0].url
    broken = Product.query.filter_by(slug="explorer-canvas-strap-watch").one()
    broken_url = broken.images[0].url
    pool = [photo(1000 + i) for i in range(60)]
    with fake_pexels(pool) as calls, \
            __import__("unittest.mock").mock.patch("velora.services.photo_check.remote_ok", _working_remote(tote_url)):
        r = seller.post("/seller/products/autofill-photos", follow_redirects=True)
    text = page(r)
    from velora.seed import OWN_PHOTOS
    own_kept = Product.query.filter(Product.slug.in_(list(OWN_PHOTOS)), Product.id.notin_(
        [p.id for p in Product.query.order_by(Product.id).limit(9)])).count()
    assert f"Added photos to {Product.query.count() - 1 - own_kept} product(s)" in text  # all but the working stock photo and the store's own photos
    db.session.expire_all()
    tote = db.session.get(Product, tote.id)
    assert [i.url for i in tote.images] == [tote_url]  # a working photo is untouched
    broken = db.session.get(Product, broken.id)
    assert broken.primary_image.filename and all(i.url != broken_url for i in broken.images)  # dead link replaced
    assert broken.primary_image.credit.startswith("Photo by ") and "Pexels" in broken.primary_image.credit
    searches = [kw["params"]["query"] for url, kw in calls if url.endswith("/search")]
    assert "blue dial dive watch" in searches and "automatic dive watch" in searches  # specific, per watch


def test_products_with_no_photo_at_all_are_filled_first(seller, keyed):
    blank_demo_photos()
    with fake_pexels([photo(3000 + i) for i in range(60)]) as calls, \
            __import__("unittest.mock").mock.patch("velora.services.photo_check.remote_ok", _working_remote()):
        seller.post("/seller/products/autofill-photos")
    first = [kw["params"]["query"] for url, kw in calls if url.endswith("/search")][:9]
    from velora.photos import PRODUCT_PHOTO_QUERIES
    blank = {PRODUCT_PHOTO_QUERIES[p.slug] for p in Product.query.order_by(Product.id).limit(9)}
    assert set(first) <= blank  # the empty ones before the ones with dead links


def test_fill_uses_different_photos_and_second_press_finishes_the_job(seller, keyed):
    pool = [photo(2000 + i) for i in range(80)]
    with fake_pexels(pool), __import__("unittest.mock").mock.patch("velora.services.photo_check.remote_ok", _working_remote()):
        seller.post("/seller/products/autofill-photos")
        seller.post("/seller/products/autofill-photos")
    db.session.expire_all()
    covers = [p.primary_image.filename or p.primary_image.url for p in Product.query.all()]
    assert all(covers) and len(set(covers)) == len(covers) == Product.query.count() == 80  # every watch has its own photo


def test_fill_does_nothing_when_every_photo_works(seller, keyed):
    for p in Product.query.all():
        for img in list(p.images):
            db.session.delete(img)
    db.session.commit()
    from velora.services import photo_check
    # give every product a local file that exists
    for p in Product.query.all():
        name = __import__("velora.services.uploads", fromlist=["x"]).save_image_bytes(jpeg(200, 300))
        db.session.add(ProductImage(product_id=p.id, filename=name, alt=p.name))
    db.session.commit()
    with fake_pexels([photo(1)]) as calls:
        r = seller.post("/seller/products/autofill-photos", follow_redirects=True)
    assert "already has a photo that loads" in page(r) and calls == []


def test_fill_works_without_a_key_when_online_and_is_staff_only(seller, client):
    with patch("velora.services.openverse.requests.get", side_effect=requests.ConnectionError("offline")), \
            patch("velora.services.photo_check.check_remote", return_value={}):
        r = seller.post("/seller/products/autofill-photos", follow_redirects=True)
    assert "Couldn't reach the free photo source" in page(r)  # no key needed; just needs the internet
    anon = client.application.test_client()
    assert anon.post("/seller/products/autofill-photos").status_code == 302
    anon.post("/account/login", data={"email": "buyer2@velora.example", "password": "Buyer123!"})
    assert anon.post("/seller/products/autofill-photos").status_code == 403


def test_fill_stops_politely_when_pexels_says_no(seller, keyed):
    with fake_pexels(status=429), __import__("unittest.mock").mock.patch("velora.services.photo_check.remote_ok", _working_remote()):
        r = seller.post("/seller/products/autofill-photos", follow_redirects=True)
    assert "free limit is 200 searches" in page(r)


def test_products_page_counts_products_without_a_photo(seller):
    blank_demo_photos()
    html = seller.get("/seller/products").get_data(as_text=True)
    n = Product.query.filter(~Product.images.any()).count()
    assert n == 9 and f"<strong>{n}</strong> products have no photo" in html
    listed = seller.get("/seller/products?nophoto=1").get_data(as_text=True)
    assert "Minimalist Leather Strap Watch" in listed and "Smart Fitness Watch" not in listed


def test_photo_check_really_works_in_worker_threads(app):
    """Regression: the check runs in threads that have no Flask app context (it once crashed there)."""
    from unittest.mock import MagicMock, patch
    from velora.services import photo_check

    def fake_get(url, **kw):
        assert "VeloraMarket" in kw["headers"]["User-Agent"]
        r = MagicMock()
        r.status_code = 200 if "good" in url else 404
        r.headers = {"Content-Type": "image/jpeg" if "good" in url else "text/html"}
        return r

    with patch("velora.services.photo_check.requests.get", side_effect=fake_get):
        status = photo_check.check_remote([f"https://x.example/good{i}.jpg" for i in range(12)] + ["https://x.example/bad.jpg"])
    assert sum(status.values()) == 12 and status["https://x.example/bad.jpg"] is False


def test_fill_looks_at_a_second_page_when_the_first_is_all_used(seller, keyed):
    """If every photo on page 1 is already taken by another product, page 2 is tried before giving up."""
    from unittest.mock import patch
    from .test_pexels_photos import FakeResp
    shades = Product.query.filter_by(slug="diver-automatic-200m").one()
    for other in Product.query.filter(Product.id != shades.id):
        db.session.delete(other)
    db.session.commit()
    page1 = [photo(1), photo(2)]
    page2 = [photo(3, w=800, h=1200)]
    seen = []

    def fake_get(url, **kw):
        if "images.pexels.com" in url:
            return FakeResp(content=jpeg())
        if url.endswith("/search"):
            n = kw["params"]["page"]
            seen.append(n)
            return FakeResp(data={"total_results": 40, "photos": page1 if n == 1 else page2})
        return FakeResp(status=404, data={})

    with patch("velora.services.pexels.requests.get", side_effect=fake_get), \
            patch("velora.services.photo_check.remote_ok", _working_remote()):
        from velora.blueprints import seller as seller_module
        assert seller_module._pick_photo("fashion model", used={1, 2}).id == 3  # page 1 exhausted -> page 2
    assert seen == [1, 2]
