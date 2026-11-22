"""The Spectrum Chronograph: ten colour editions, each with its own photo and a drag-to-turn 360° view."""
import html
import json
import re

from velora.extensions import db
from velora.models import Product
from velora.spin import spin_data

COLOURS = ["Black", "White", "Blue", "Red", "Green", "Purple", "Pink", "Orange", "Yellow", "Teal"]


def _spin_json(page):
    raw = re.search(r'data-spin-data="([^"]*)"', page).group(1)
    return json.loads(html.unescape(raw))


def test_the_watch_is_in_the_shop_with_ten_colours(client):
    p = Product.query.filter_by(slug="spectrum-chronograph").one()
    assert p.category.slug == "chronographs" and p.color_list == COLOURS and p.offers_engraving
    assert [i.url for i in p.images] == [f"/static/img/watches/spectrum-{c.lower()}.webp" for c in COLOURS]
    listing = client.get("/shop/c/chronographs").get_data(as_text=True)
    assert "Spectrum Chronograph" in listing and "/static/img/watches/spectrum-black.webp" in listing


def test_every_colour_has_a_photo_and_360_frames_that_load(client, app):
    data = spin_data(Product.query.filter_by(slug="spectrum-chronograph").one())
    assert data["order"] == COLOURS
    for name in COLOURS:
        c = data["colours"][name]
        assert c["main"] == f"/static/img/watches/spectrum-{name.lower()}.webp"
        assert len(c["frames"]) == 6
        for url in [c["main"], *c["frames"]]:
            assert client.get(url.split("?")[0]).status_code == 200, url


def test_product_page_has_the_360_viewer_and_colour_thumbnails(client):
    page = client.get("/shop/p/spectrum-chronograph").get_data(as_text=True)
    assert "data-spin-toggle" in page and "360° View" in page and 'role="slider"' in page
    assert "js/spin.js" in page
    data = _spin_json(page)
    assert data["order"] == COLOURS and len(data["colours"]["Teal"]["frames"]) == 6
    for name in COLOURS:
        assert f'data-color="{name}"' in page  # clicking a colour photo picks that colour
        assert f'name="color" value="{name}"' in page


def test_watches_without_frames_have_no_360_viewer(client):
    page = client.get("/shop/p/diver-automatic-200m").get_data(as_text=True)
    assert "data-spin" not in page and "js/spin.js" not in page
    assert spin_data(Product.query.filter_by(slug="diver-automatic-200m").one()) is None


def test_a_colour_without_frames_is_left_out_of_the_360_view(app):
    p = Product.query.filter_by(slug="spectrum-chronograph").one()
    p.colors = "Black,Gold"  # the seller added a colour that has no 360° frames yet
    db.session.commit()
    assert spin_data(p)["order"] == ["Black"]


def test_buying_a_colour_edition_with_engraving(customer):
    p = Product.query.filter_by(slug="spectrum-chronograph").one()
    r = customer.post(f"/cart/add/{p.id}", data={"quantity": 1, "size": "44 mm", "color": "Teal", "engraving": "GO"},
                      headers={"X-Requested-With": "fetch"})
    assert r.json["ok"] and "44 mm · Teal · Engraved “GO”" in r.json["drawer"]


def test_spin_script_supports_drag_touch_keys_and_reduced_motion(client):
    js = client.get("/static/js/spin.js").get_data(as_text=True)
    for needle in ("pointerdown", "pointermove", "setPointerCapture", "ArrowLeft", "prefers-reduced-motion", "opacity"):
        assert needle in js, needle
    css = client.get("/static/css/app.css").get_data(as_text=True)
    assert "touch-action: pan-y" in css  # vertical page scrolling still works on phones
