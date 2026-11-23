"""Open every link the site shows, as a visitor, a buyer, a seller and the admin: no page may be missing (404) or crash
(500). This is the "no broken routes across core user workflows" check."""
import re
from collections import deque
from urllib.parse import urldefrag, urlparse

import pytest

from .conftest import login

LINK = re.compile(r'href="([^"]+)"')
SKIP = ("/static/", "/media/", "/account/logout", "/seller/export/", "mailto:", "tel:", "javascript:")


def crawl(client, start=("/",), limit=700):
    seen, broken, queue = set(), [], deque(start)
    while queue and len(seen) < limit:
        url = queue.popleft()
        path = urlparse(url).path
        key = path if "page=" not in url else url  # one visit per page; query variants only for paging
        if key in seen:
            continue
        seen.add(key)
        resp = client.get(url, follow_redirects=True)
        if resp.status_code >= 400:
            broken.append(f"{url} -> {resp.status_code}")
            continue
        if "text/html" not in resp.content_type:
            continue
        for href in LINK.findall(resp.get_data(as_text=True)):
            href = urldefrag(href.replace("&amp;", "&"))[0]
            if not href.startswith("/") or href.startswith("//") or any(s in href for s in SKIP):
                continue
            if href not in seen:
                queue.append(href)
    return seen, broken


def test_visitor_never_hits_a_broken_page(client):
    seen, broken = crawl(client)
    assert len(seen) > 60 and broken == []


@pytest.mark.parametrize("who,password,switch,start", [
    ("buyer1@velora.example", "Buyer123!", False, ["/", "/account/"]),
    ("buyer1@velora.example", "Buyer123!", True, ["/", "/seller/"]),   # their seller profile
    ("admin@velora.example", "Admin123!", False, ["/", "/admin/", "/seller/"]),
])
def test_signed_in_roles_never_hit_a_broken_page(client, who, password, switch, start):
    assert login(client, who, password).status_code == 302
    if switch:
        assert client.post("/account/switch-profile").status_code == 302
    seen, broken = crawl(client, start)
    assert len(seen) > 40 and broken == [], broken


def test_an_old_notification_about_a_removed_watch_goes_to_the_shop(customer):
    from velora.extensions import db
    from velora.models import Notification, User
    buyer = User.query.filter_by(email="buyer1@velora.example").one()
    note = Notification(user_id=buyer.id, title="Old", body="", link="/shop/p/crystal-bezel-watch")
    db.session.add(note)
    db.session.commit()
    r = customer.get(f"/account/notifications/{note.id}", follow_redirects=True)
    assert r.status_code == 200 and "sold any more" in r.get_data(as_text=True)
