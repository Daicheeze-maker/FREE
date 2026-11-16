"""Find photos (Pexels). The API is always faked here: no network and no real key are needed."""
import html as htmllib
import io
import re
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

import pytest
import requests
from PIL import Image

from velora.extensions import db
from velora.models import ApiStatus, Product, StoreSetting
from velora.services import pexels

KEY = "k" * 40


class FakeResp:
    def __init__(self, status=200, data=None, content=b""):
        self.status_code, self._data, self.content = status, data, content

    def json(self):
        return self._data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(str(self.status_code))

    def iter_content(self, size):
        for i in range(0, len(self.content), size):
            yield self.content[i:i + size]


def jpeg(w=800, h=1200, color=(120, 60, 90)):
    buf = io.BytesIO()
    Image.new("RGB", (w, h), color).save(buf, "JPEG")
    return buf.getvalue()


def photo(pid, w=800, h=1200, host="images.pexels.com", who="Ana Reyes"):
    return {"id": pid, "width": w, "height": h, "url": f"https://www.pexels.com/photo/{pid}/", "photographer": who,
            "alt": f"model {pid}", "src": {"portrait": f"https://{host}/photos/{pid}/portrait.jpeg",
                                           "medium": f"https://{host}/photos/{pid}/medium.jpeg"}}


@contextmanager
def fake_pexels(photos=(), image=None, status=200, meta=None, error=None):
    """Patch requests.get as Pexels would answer. Yields the list of calls made."""
    calls = []
    by_id = {p["id"]: p for p in photos}

    def fake_get(url, **kw):
        calls.append((url, kw))
        if error:
            raise error
        if "images.pexels.com" in url or "evil.example" in url:
            return FakeResp(content=image if image is not None else jpeg())
        if status != 200:
            return FakeResp(status=status, data={})
        if url.endswith("/search"):
            return FakeResp(data={"total_results": len(photos), "photos": list(photos)})
        m = re.search(r"/photos/(\d+)$", url)
        if m and int(m.group(1)) in by_id:
            return FakeResp(data=meta or by_id[int(m.group(1))])
        return FakeResp(status=404, data={})

    with patch("velora.services.pexels.requests.get", side_effect=fake_get):
        yield calls


@pytest.fixture()
def ready(app):
    app.config["PEXELS_API_KEY"] = KEY
    return app


def page(response):
    """The page text with HTML escapes undone, so assertions can use normal apostrophes."""
    return htmllib.unescape(response.get_data(as_text=True))


def setting(key):
    db.session.expire_all()
    row = db.session.get(StoreSetting, key)
    return row.value if row else None


# ---------------------------------------------------------------- access & setup

def test_find_photos_is_for_staff_only(client):
    assert client.get("/seller/find-photos").status_code == 302  # guest -> sign in
    client.post("/account/login", data={"email": "buyer1@velora.example", "password": "Buyer123!"})
    assert client.get("/seller/find-photos").status_code == 403  # buyer profile
    assert client.post("/seller/find-photos/use", data={}).status_code == 403
    assert client.post("/seller/photos/autofill").status_code == 403


def test_without_a_key_the_page_explains_the_free_signup(seller):
    html = seller.get("/seller/find-photos?target=slot:hero").get_data(as_text=True)
    assert "pexels.com/api" in html and "Save key" in html and "Use this photo" not in html


def test_key_is_validated_saved_hidden_and_removable(seller):
    assert "doesn't look like a Pexels key" in page(seller.post("/seller/pexels-key", data={"key": "bad key!"}, follow_redirects=True))
    with fake_pexels(status=401):  # Pexels rejects it: not kept
        r = seller.post("/seller/pexels-key", data={"key": KEY}, follow_redirects=True)
    assert "didn't accept that key" in page(r) and setting("pexels_api_key") is None
    with fake_pexels([photo(1)]):
        r = seller.post("/seller/pexels-key", data={"key": KEY}, follow_redirects=True)
    assert "key saved" in page(r) and setting("pexels_api_key") == KEY
    body = seller.get("/seller/find-photos").get_data(as_text=True)
    assert KEY not in body and "Remove saved Pexels key" in body  # never shown again
    seller.post("/seller/pexels-key", data={"action": "remove"})
    assert setting("pexels_api_key") is None


# ------------------------------------------------------------------------ search

def test_search_shows_photos_with_photographers(seller, ready):
    with fake_pexels([photo(11, who="Ana Reyes"), photo(12, who="Luis Tan")]) as calls:
        html = seller.get("/seller/find-photos?target=slot:hero&q=fashion+model").get_data(as_text=True)
    assert "Ana Reyes" in html and "Luis Tan" in html and html.count("Use this photo") == 2
    assert "Choosing a photo for: <strong>Homepage hero</strong>" in html
    url, kw = calls[0]
    assert url.endswith("/search") and kw["params"]["query"] == "fashion model" and kw["params"]["orientation"] == "portrait"
    assert kw["headers"]["Authorization"] == KEY and "VeloraMarket" in kw["headers"]["User-Agent"]


def test_search_defaults_to_a_sensible_query_per_target(seller, ready):
    with fake_pexels([photo(1)]) as calls:
        seller.get("/seller/find-photos?target=slot:hero")
    assert calls[0][1]["params"]["query"] == "fashion model portrait studio"
    shades = Product.query.filter_by(slug="tortoiseshell-sunglasses").one()
    with fake_pexels([photo(1)]) as calls:
        seller.get(f"/seller/find-photos?target=product:{shades.id}")
    assert calls[0][1]["params"]["query"] == "tortoiseshell sunglasses"  # specific to the product


def test_search_drops_photos_from_other_hosts(app):
    with app.test_request_context():
        assert pexels.parse_photo(photo(1)) is not None
        assert pexels.parse_photo(photo(2, host="evil.example")) is None
        assert pexels.parse_photo({"id": "x"}) is None and pexels.parse_photo("nope") is None
        bad = photo(3)
        bad["src"]["portrait"] = "http://images.pexels.com/p.jpg"  # plain http is refused too
        assert pexels.parse_photo(bad) is None


@pytest.mark.parametrize("status, text", [(401, "didn't accept that key"), (429, "200 searches an hour")])
def test_search_errors_are_explained(seller, ready, status, text):
    with fake_pexels(status=status):
        html = seller.get("/seller/find-photos?target=slot:hero").get_data(as_text=True)
    assert text in htmllib.unescape(html)
    db.session.expire_all()
    assert ApiStatus.query.filter_by(name="pexels").one().error_count >= 1


def test_offline_is_explained_and_nothing_breaks(seller, ready):
    with fake_pexels(error=requests.ConnectionError("no internet")):
        r = seller.get("/seller/find-photos?target=slot:hero")
    assert r.status_code == 200 and "Couldn't reach Pexels" in page(r)
    assert seller.get("/seller/photos").status_code == 200


# ------------------------------------------------------------------ using a photo

def test_use_photo_for_a_site_spot_saves_it_locally_with_credit(seller, ready):
    with fake_pexels([photo(21, who="Ana Reyes")]):
        r = seller.post("/seller/find-photos/use", data={"target": "slot:hero", "photo_id": 21})
    assert r.status_code == 302 and r.headers["Location"].endswith("/seller/photos")
    name = setting("photo_hero")
    assert name.endswith(".webp") and setting("photo_hero_credit") == "Photo by Ana Reyes on Pexels"
    assert (Path(seller.application.config["UPLOAD_FOLDER"]) / name).is_file()  # stored in the project
    home = seller.get("/").get_data(as_text=True)
    assert f"/media/{name}" in home and "images.pexels.com" not in home  # served from the store, not Pexels
    assert "Photo by Ana Reyes on Pexels" in seller.get("/pages/about").get_data(as_text=True)


def test_replacing_a_photo_deletes_the_old_file_and_own_uploads_clear_the_credit(seller, ready):
    folder = Path(seller.application.config["UPLOAD_FOLDER"])
    with fake_pexels([photo(31), photo(32)]):
        seller.post("/seller/find-photos/use", data={"target": "slot:hero", "photo_id": 31})
        first = setting("photo_hero")
        seller.post("/seller/find-photos/use", data={"target": "slot:hero", "photo_id": 32})
    assert setting("photo_hero") != first and not (folder / first).exists()
    buf = io.BytesIO(jpeg())
    seller.post("/seller/photos/hero", data={"photo": (buf, "mine.jpg")}, content_type="multipart/form-data")
    assert setting("photo_hero_credit") is None  # your own photo has no Pexels credit
    with fake_pexels([photo(33)]):
        seller.post("/seller/find-photos/use", data={"target": "slot:promo", "photo_id": 33})
    seller.post("/seller/photos/promo/reset")
    assert setting("photo_promo") is None and setting("photo_promo_credit") is None


def test_use_photo_as_a_product_cover(seller, ready):
    p = Product.query.filter_by(slug="minimalist-leather-strap-watch").one()
    old_cover = p.primary_image.url
    with fake_pexels([photo(41, who="Mia Cruz")]):
        r = seller.post("/seller/find-photos/use", data={"target": f"product:{p.id}", "photo_id": 41})
    assert r.status_code == 302 and f"/seller/products/{p.id}" in r.headers["Location"]
    db.session.expire_all()
    p = db.session.get(Product, p.id)
    assert p.primary_image.filename and p.primary_image.credit == "Photo by Mia Cruz on Pexels"
    assert p.images[1].url == old_cover  # the previous photo moves behind the new cover
    html = seller.get(f"/shop/p/{p.slug}").get_data(as_text=True)
    assert "Photo by Mia Cruz on Pexels" in html


def test_photo_details_come_from_pexels_not_from_the_browser(seller, ready):
    """Only the photo id is accepted from the form: a forged URL or credit is ignored."""
    with fake_pexels([photo(51, who="Real Photographer")]) as calls:
        seller.post("/seller/find-photos/use", data={"target": "slot:hero", "photo_id": 51, "image": "https://evil.example/x.jpg",
                                                     "credit": "Photo by Forged on Pexels"})
    assert setting("photo_hero_credit") == "Photo by Real Photographer on Pexels"
    assert all("evil.example" not in url for url, _ in calls)


def test_a_photo_hosted_elsewhere_is_never_downloaded(seller, ready):
    bad = photo(61, host="evil.example")
    with fake_pexels([bad], meta=bad) as calls:
        r = seller.post("/seller/find-photos/use", data={"target": "slot:hero", "photo_id": 61}, follow_redirects=True)
    assert "can't use" in page(r) and setting("photo_hero") is None
    assert not any("evil.example" in url for url, _ in calls)


def test_bad_downloads_are_rejected(seller, ready):
    with fake_pexels([photo(71)], image=b"<html>not an image</html>"):
        r = seller.post("/seller/find-photos/use", data={"target": "slot:hero", "photo_id": 71}, follow_redirects=True)
    assert "isn't a valid image" in page(r) and setting("photo_hero") is None
    ready.config["PHOTO_DOWNLOAD_MAX_MB"] = 0  # anything is "too large"
    with fake_pexels([photo(72)]):
        r = seller.post("/seller/find-photos/use", data={"target": "slot:hero", "photo_id": 72}, follow_redirects=True)
    assert "too large" in page(r) and setting("photo_hero") is None


def test_use_rejects_bad_requests(seller, ready):
    assert seller.post("/seller/find-photos/use", data={"target": "slot:nope", "photo_id": 1}).status_code == 400
    assert seller.post("/seller/find-photos/use", data={"target": "slot:hero", "photo_id": "abc"}).status_code == 400
    assert seller.post("/seller/find-photos/use", data={"target": "product:999999", "photo_id": 1}).status_code == 400


# ---------------------------------------------------------------------- auto-fill

def test_autofill_fills_every_empty_spot_with_different_photos(seller, ready):
    pool = [photo(100 + i) for i in range(8)]
    with fake_pexels(pool):
        r = seller.post("/seller/photos/autofill", follow_redirects=True)
    assert "Filled 5 site photo(s)" in page(r)
    names = [setting(f"photo_{s}") for s in ("hero", "lookbook", "promo", "login", "register")]
    assert all(n and n.endswith(".webp") for n in names) and len(set(names)) == 5
    credits = [setting(f"photo_{s}_credit") for s in ("hero", "lookbook", "promo", "login", "register")]
    assert all(c == "Photo by Ana Reyes on Pexels" for c in credits)


def test_autofill_never_overwrites_a_photo_that_is_already_set(seller, ready):
    seller.post("/seller/photos/hero", data={"photo": (io.BytesIO(jpeg()), "mine.jpg")}, content_type="multipart/form-data")
    mine = setting("photo_hero")
    with fake_pexels([photo(200 + i) for i in range(8)]):
        seller.post("/seller/photos/autofill")
    assert setting("photo_hero") == mine and setting("photo_lookbook")


def test_autofill_stops_politely_when_pexels_fails(seller, ready):
    with fake_pexels(status=429):
        r = seller.post("/seller/photos/autofill", follow_redirects=True)
    assert "Stopped after 0 photo(s)" in page(r) and setting("photo_hero") is None


def test_autofill_without_a_key_points_to_setup(seller):
    r = seller.post("/seller/photos/autofill", follow_redirects=True)
    assert "Add your free Pexels key" in page(r)


# ------------------------------------------------- placeholders and honest copy

def test_site_spots_show_a_catalog_photo_until_a_real_photo_is_chosen(client):
    home = client.get("/").get_data(as_text=True)
    assert "model-placeholder.svg" not in home.split("hero__photo")[1][:300]  # real catalog photo, not a blank card
    assert client.get("/static/img/model-placeholder.svg").status_code == 200


def test_the_wrong_sneaker_photo_is_gone(app):
    shoes = Product.query.filter_by(slug="red-runner-sneakers").one()
    assert shoes.images == []  # blank until a real photo is chosen (the old one showed toe shoes)


def test_copy_no_longer_claims_the_team_models_the_photos(client):
    for url in ("/", "/pages/about", "/pages/faq", "/shop/"):
        text = page(client.get(url)).lower()
        assert "modelled by our" not in text and "worn by our team" not in text and "model every piece ourselves" not in text, url
    assert "pexels" in client.get("/pages/faq").get_data(as_text=True).lower()


# --------------------------------------------------------------------- admin page

def test_admin_api_health_lists_pexels_and_can_test_it(admin, ready):
    html = admin.get("/admin/api-health").get_data(as_text=True)
    assert "Pexels" in html and "/admin/api-health/pexels/test" in html
    with fake_pexels([photo(1)]):
        r = admin.post("/admin/api-health/pexels/test", follow_redirects=True)
    assert "Pexels OK" in page(r)
    with fake_pexels(status=401):
        r = admin.post("/admin/api-health/pexels/test", follow_redirects=True)
    assert "Pexels unavailable" in page(r)
