"""60 more watches (10 per collection), each with its own photo and an 8-frame 360° view."""
from collections import Counter

from velora.catalog_more import MORE
from velora.models import Category, Product
from velora.services.catalog import slugify
from velora.spin import spin_data


def test_ten_new_watches_in_every_collection():
    assert len(MORE) == 60 and len({r[1] for r in MORE}) == 60
    assert Counter(r[0].split("-")[0] for r in MORE) == {c: 10 for c in ("dress", "dive", "chrono", "field", "smart", "ladies")}


def test_every_new_watch_has_its_photo_and_360_view(client):
    for r in MORE:
        p = Product.query.filter_by(slug=slugify(r[1])).one()
        url = f"/static/img/watches/{p.slug}-{slugify(r[14])}.webp"
        assert p.primary_image.url == url, p.name
        assert client.get(url).status_code == 200, url
        data = spin_data(p)
        assert data and data["order"] == [r[14]] and len(data["colours"][r[14]]["frames"]) == 8, p.name
        assert data["colours"][r[14]]["main"] == url
        assert p.size_list and p.color_list == [r[14]]
        assert p.stock > 0


def test_new_watch_pages_show_the_360_viewer(client):
    for slug in ("riviera-blue-chrono-41", "pulse-summit-rugged", "etoile-diamond-30", "guilloche-date-37"):
        page = client.get(f"/shop/p/{slug}").get_data(as_text=True)
        assert "data-spin-toggle" in page and "360° View" in page, slug


def test_collection_pages_list_the_new_watches(client):
    page = client.get("/shop/c/smart-watches?page=1").get_data(as_text=True)
    assert "Pulse Active" in page or "Pulse Summit Rugged" in page
    assert Product.query.join(Category).filter(Category.slug == "ladies-watches").count() == 13


def test_accented_names_get_plain_web_addresses():
    assert slugify("Étoile Diamond 30") == "etoile-diamond-30"
    assert slugify("Guilloché Date 37") == "guilloche-date-37"


def test_sharp_frames_fill_the_viewer_and_soft_ones_stay_smaller(client):
    assert 'class="spin" data-spin' in client.get("/shop/p/riviera-blue-chrono-41").get_data(as_text=True)
    assert 'class="spin spin--soft" data-spin' in client.get("/shop/p/spectrum-chronograph").get_data(as_text=True)
