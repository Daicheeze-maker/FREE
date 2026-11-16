"""Every product in the right collection, a safe refresh for older databases, and filling missing photos."""
import re

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
    assert ordered == ["Women", "Men", "Shoes", "Accessories", "Watches", "Jewelry", "Bags", "Gifts & Gourmet"]


def test_sneakers_and_sunglasses_are_no_longer_under_clothing(app):
    clothing = names("men") + names("women")
    assert not any(w in n for n in clothing for w in ("Sneakers", "Sunglasses", "Boots", "Belt", "Scarf", "Bag", "Watch"))
    assert "Red Runner Sneakers" in names("shoes") and "Tortoiseshell Sunglasses" in names("accessories")
    assert names("men") == ["Heavyweight White Tee", "Tailored Wool Suit", "Utility Field Jacket"]
    assert len(names("women")) == 4


def test_every_product_matches_its_collection(app):
    rules = {"women": ("Dress", "Jeans", "Jacket"), "men": ("Suit", "Tee", "Jacket"),
             "shoes": ("Sneakers", "Boots", "Loafers", "Sandals"), "accessories": ("Sunglasses", "Belt", "Scarf", "Card Holder"),
             "watches": ("Watch", "Diver"), "jewelry": ("Rings", "Earrings", "Pendant", "Bracelet", "Jewelry"),
             "bags": ("Tote", "Crossbody", "Backpack", "Clutch", "Duffel"),
             "gifts-gourmet": ("Gift Box", "Chocolate", "Coffee", "Candle")}
    seen = 0
    for slug, words in rules.items():
        for name in names(slug):
            seen += 1
            assert any(w in name for w in words), (slug, name)
    assert seen == Product.query.count() == 36  # nothing is outside a rule


def test_new_collections_have_real_items_with_sizes(app):
    assert len(names("shoes")) == 5 and len(names("accessories")) == 5
    assert Product.query.filter_by(slug="suede-chelsea-boots").one().size_list[0] == "39"
    assert Product.query.filter_by(slug="block-heel-leather-sandals").one().size_list == ["36", "37", "38", "39", "40", "41"]
    assert Product.query.filter_by(slug="italian-leather-belt").one().size_list == ["85", "90", "95", "100", "105"]
    assert Product.query.filter_by(slug="aviator-sunglasses").one().size_list == []


def test_the_wrong_sunglasses_photo_is_gone(app):
    shades = Product.query.filter_by(slug="tortoiseshell-sunglasses").one()
    assert shades.images == []  # the old one showed plain black glasses


def test_menus_show_the_new_collections(client):
    html = client.get("/").get_data(as_text=True)
    nav = html.split("header__nav")[1].split("</nav>")[0]
    assert all(w in nav for w in ("Clothing", "Shoes", "Accessories", "Watches", "Jewelry", "Bags"))
    clothing_menu = re.search(r"dropdown__panel--mega.*?</div>\s*</div>", nav, re.S).group(0)
    assert "Women" in clothing_menu and "Men" in clothing_menu and "Shoes" not in clothing_menu
    assert "/shop/c/shoes" in html and "/shop/c/accessories" in html
    for url in ("/shop/c/shoes", "/shop/c/accessories"):
        r = client.get(url)
        assert r.status_code == 200 and "pcard" in r.get_data(as_text=True)


# --------------------------------------------- refreshing an older database safely

def _old_catalog(app):
    """Put the database back the way the previous release left it (no Shoes/Accessories, misfits under Men)."""
    men = Category.query.filter_by(slug="men").one()
    for slug in ("red-runner-sneakers", "tortoiseshell-sunglasses"):
        Product.query.filter_by(slug=slug).one().category = men
    new = ("white-leather-court-sneakers", "suede-chelsea-boots", "classic-leather-loafers", "block-heel-leather-sandals",
           "aviator-sunglasses", "italian-leather-belt", "printed-silk-scarf", "leather-card-holder")
    for slug in new:
        db.session.delete(Product.query.filter_by(slug=slug).one())
    db.session.flush()
    for slug in ("shoes", "accessories"):
        db.session.delete(Category.query.filter_by(slug=slug).one())
    for pos, c in enumerate(Category.query.order_by(Category.position)):
        c.position = pos
    shades = Product.query.filter_by(slug="tortoiseshell-sunglasses").one()
    shades.images.append(ProductImage(url="https://images.unsplash.com/photo-1572635196237-14b3f281503f?w=900", alt="x"))
    db.session.commit()


def test_refresh_fixes_an_older_catalog_and_keeps_everything_else(tmp_path):
    app = create_app("testing", SQLALCHEMY_DATABASE_URI=f"sqlite:///{tmp_path / 'old.db'}")
    with app.app_context():
        init_database()
        seed()
        _old_catalog(app)
        db.session.add(StoreSetting(key="photo_hero", value="mine.webp"))  # work the user already did
        db.session.commit()
        assert demo_status() == "stale"
        before = (Order.query.count(), User.query.count())
    out = app.test_cli_runner().invoke(args=["upgrade-demo"]).output  # no --yes, no keyboard: must NOT need a prompt
    assert "moved Red Runner Sneakers to Shoes" in out and "moved Tortoiseshell Sunglasses to Accessories" in out
    assert "OLDER VERSION" not in out
    with app.app_context():
        assert demo_status() == "current"
        assert names("men") == ["Heavyweight White Tee", "Tailored Wool Suit", "Utility Field Jacket"]
        assert len(names("shoes")) == 5 and len(names("accessories")) == 5
        assert Product.query.filter_by(slug="tortoiseshell-sunglasses").one().images == []
        assert (Order.query.count(), User.query.count()) == before  # nothing deleted
        assert db.session.get(StoreSetting, "photo_hero").value == "mine.webp"
        assert [c.name for c in Category.query.order_by(Category.position)][2:4] == ["Shoes", "Accessories"]
    again = app.test_cli_runner().invoke(args=["upgrade-demo"]).output
    assert "Catalog updated" not in again  # idempotent: the second start changes nothing


def test_refresh_never_changes_a_catalog_that_is_already_right(app):
    assert demo_status() == "current"
    assert refresh_catalog() == []


def test_refresh_keeps_a_seller_s_own_edits(tmp_path):
    app = create_app("testing", SQLALCHEMY_DATABASE_URI=f"sqlite:///{tmp_path / 'edits.db'}")
    with app.app_context():
        init_database()
        seed()
        _old_catalog(app)
        belt_less = Product.query.filter_by(slug="structured-leather-tote").one()
        belt_less.price_minor = 123_400  # the seller changed a price
        db.session.commit()
        refresh_catalog()
        assert Product.query.filter_by(slug="structured-leather-tote").one().price_minor == 123_400


# ------------------------------------------------------ fill missing & broken photos

def _working_remote(*urls):
    """Pretend only these remote photo links load."""
    return lambda url, timeout=6, user_agent=None: url in urls


@pytest.fixture()
def keyed(app):
    app.config["PEXELS_API_KEY"] = KEY
    return app


def test_fill_gives_photos_to_missing_and_broken_ones_and_leaves_working_ones(seller, keyed):
    tote = Product.query.filter_by(slug="structured-leather-tote").one()
    tote_url = tote.images[0].url
    broken = Product.query.filter_by(slug="linen-wrap-midi-dress").one()
    broken_url = broken.images[0].url
    pool = [photo(1000 + i) for i in range(60)]
    with fake_pexels(pool) as calls, \
            __import__("unittest.mock").mock.patch("velora.services.photo_check.remote_ok", _working_remote(tote_url)):
        r = seller.post("/seller/products/autofill-photos", follow_redirects=True)
    text = page(r)
    assert "Added photos to 30 product(s)" in text and "5 more are left" in text  # capped to stay under Pexels' hourly limit
    db.session.expire_all()
    tote = db.session.get(Product, tote.id)
    assert [i.url for i in tote.images] == [tote_url]  # a working photo is untouched
    broken = db.session.get(Product, broken.id)
    assert broken.primary_image.filename and all(i.url != broken_url for i in broken.images)  # dead link replaced
    assert broken.primary_image.credit.startswith("Photo by ") and "Pexels" in broken.primary_image.credit
    searches = [kw["params"]["query"] for url, kw in calls if url.endswith("/search")]
    assert "tortoiseshell sunglasses" in searches and "red running sneakers" in searches  # specific, per product


def test_products_with_no_photo_at_all_are_filled_first(seller, keyed):
    with fake_pexels([photo(3000 + i) for i in range(60)]) as calls, \
            __import__("unittest.mock").mock.patch("velora.services.photo_check.remote_ok", _working_remote()):
        seller.post("/seller/products/autofill-photos")
    first = [kw["params"]["query"] for url, kw in calls if url.endswith("/search")][:9]
    blank = {"red running sneakers", "tortoiseshell sunglasses", "white leather sneakers", "suede chelsea boots", "leather loafers",
             "block heel sandals", "aviator sunglasses", "leather belt", "silk scarf", "leather card holder wallet"}
    assert set(first) <= blank  # the empty ones before the ones with dead links


def test_fill_uses_different_photos_and_second_press_finishes_the_job(seller, keyed):
    pool = [photo(2000 + i) for i in range(80)]
    with fake_pexels(pool), __import__("unittest.mock").mock.patch("velora.services.photo_check.remote_ok", _working_remote()):
        seller.post("/seller/products/autofill-photos")
        seller.post("/seller/products/autofill-photos")
    db.session.expire_all()
    covers = [p.primary_image.filename for p in Product.query.all()]
    assert all(covers) and len(set(covers)) == len(covers) == 36  # every product has its own photo


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


def test_fill_needs_a_key_and_staff_access(seller, client):
    r = seller.post("/seller/products/autofill-photos", follow_redirects=True)
    assert "Add your free Pexels key first" in page(r)
    anon = client.application.test_client()
    assert anon.post("/seller/products/autofill-photos").status_code == 302
    anon.post("/account/login", data={"email": "buyer2@velora.example", "password": "Buyer123!"})
    assert anon.post("/seller/products/autofill-photos").status_code == 403


def test_fill_stops_politely_when_pexels_says_no(seller, keyed):
    with fake_pexels(status=429), __import__("unittest.mock").mock.patch("velora.services.photo_check.remote_ok", _working_remote()):
        r = seller.post("/seller/products/autofill-photos", follow_redirects=True)
    assert "Stopped after 0 product(s)" in page(r)


def test_products_page_counts_products_without_a_photo(seller):
    html = seller.get("/seller/products").get_data(as_text=True)
    n = Product.query.filter(~Product.images.any()).count()
    assert n >= 9 and f"<strong>{n}</strong> products have no photo" in html  # the 2 misfits + 7 new ones... all listed
    listed = seller.get("/seller/products?nophoto=1").get_data(as_text=True)
    assert "Red Runner Sneakers" in listed and "Structured Leather Tote" not in listed


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
    shades = Product.query.filter_by(slug="tortoiseshell-sunglasses").one()
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
