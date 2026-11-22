"""The drag-to-turn 360° view on the store's watches."""
import html
import json
import re

from velora.extensions import db
from velora.models import Product
from velora.spin import spin_data

W = "riviera-blue-chrono-41"  # one of the store's watches, with its generated photo and 8 frames per turn


def _spin_json(page):
    raw = re.search(r'data-spin-data="([^"]*)"', page).group(1)
    return json.loads(html.unescape(raw))


def test_every_watch_has_a_photo_and_360_frames_that_load(client, app):
    p = Product.query.filter_by(slug=W).one()
    data = spin_data(p)
    assert data["order"] == ["Blue"] and data["soft"] is False
    c = data["colours"]["Blue"]
    assert c["main"] == "/static/img/watches/riviera-blue-chrono-41-blue.webp" and len(c["frames"]) == 8
    for url in [c["main"], *c["frames"]]:
        assert client.get(url.split("?")[0]).status_code == 200, url


def test_product_page_has_the_360_viewer_and_colour_thumbnail(client):
    page = client.get(f"/shop/p/{W}").get_data(as_text=True)
    assert "data-spin-toggle" in page and "360° View" in page and 'role="slider"' in page
    assert "js/spin.js" in page
    assert _spin_json(page)["order"] == ["Blue"]
    assert 'name="color" value="Blue"' in page


def test_watches_without_frames_have_no_360_viewer(seller):
    from velora.models import Category
    db.session.add(Product(name="My Own Watch", slug="my-own-watch", sku="OWN-1", brand="Me", category=Category.query.first(),
                           price_minor=100000, stock=2, short_description="x", description="x"))
    db.session.commit()
    page = seller.get("/shop/p/my-own-watch").get_data(as_text=True)
    assert "data-spin" not in page and "js/spin.js" not in page
    assert spin_data(Product.query.filter_by(slug="my-own-watch").one()) is None


def test_a_colour_without_frames_is_left_out_of_the_360_view(app):
    p = Product.query.filter_by(slug=W).one()
    p.colors = "Blue,Gold"  # the seller added a colour that has no 360° frames yet
    db.session.commit()
    assert spin_data(p)["order"] == ["Blue"]


def test_buying_a_watch_with_engraving(customer):
    p = Product.query.filter_by(slug=W).one()
    r = customer.post(f"/cart/add/{p.id}", data={"quantity": 1, "size": "41 mm", "color": "Blue", "engraving": "GO"},
                      headers={"X-Requested-With": "fetch"})
    assert r.json["ok"] and "41 mm · Blue · Engraved “GO”" in r.json["drawer"]


def test_spin_script_supports_drag_touch_keys_and_reduced_motion(client):
    js = client.get("/static/js/spin.js").get_data(as_text=True)
    for needle in ("pointerdown", "pointermove", "setPointerCapture", "ArrowLeft", "prefers-reduced-motion", "opacity"):
        assert needle in js, needle
    css = client.get("/static/css/app.css").get_data(as_text=True)
    assert "touch-action: pan-y" in css  # vertical page scrolling still works on phones


def test_start_up_removes_the_old_watches_and_adds_missing_ones_keeping_the_seller_s(tmp_path):
    """An older store (the first 20 watches + Spectrum) becomes the store of generated watches; a seller's own watch stays."""
    from velora import create_app
    from velora.cli import demo_status, init_database
    from velora.models import Category, ProductImage
    from velora.seed import seed
    app = create_app("testing", SQLALCHEMY_DATABASE_URI=f"sqlite:///{tmp_path / 'mine.db'}")
    with app.app_context():
        init_database()
        seed()
        db.session.delete(Product.query.filter_by(slug=W).one())  # yesterday's store didn't have it yet
        for p in Product.query.all():
            p.is_featured = False
        cat = Category.query.filter_by(slug="chronographs").one()
        old = Product(name="Spectrum Chronograph", slug="spectrum-chronograph", sku="VM-OLD-1", brand="x", category=cat,
                      price_minor=100000, stock=5, short_description="x", description="x")
        old.images.append(ProductImage(url="/static/img/watches/spectrum-black.webp", alt="x"))
        db.session.add_all([old, Product(name="My Own Watch", slug="my-own-watch", sku="OWN-1", brand="Me",
                                         category=Category.query.first(), price_minor=100000, stock=2,
                                         short_description="x", description="x")])
        db.session.commit()
        assert demo_status() == "stale"
    out = app.test_cli_runner().invoke(args=["upgrade-demo"]).output
    assert "added Riviera Blue Chrono 41" in out and "removed 1 product(s)" in out
    with app.app_context():
        assert Product.query.filter_by(slug="spectrum-chronograph").count() == 0
        assert Product.query.filter_by(slug="my-own-watch").count() == 1  # the seller's watch stays
        assert Product.query.filter_by(is_featured=True).count() == 12  # the homepage keeps its Featured row
        assert all(p.images[0].url.startswith("/static/img/watches/") for p in Product.query if p.slug != "my-own-watch")
        assert demo_status() == "current"
