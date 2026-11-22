"""Every watch has options: case size, colour and an optional engraving. They are validated on the server,
priced on the server, and follow the watch from the bag to the order."""
import re

import pytest

from velora.extensions import db
from velora.models import CartItem, Order, OrderItem, Product

from .conftest import default_address, get_user, in_stock_product, login, optioned_product

FETCH = {"X-Requested-With": "fetch"}


def _checkout(client, email="buyer1@velora.example"):
    page = client.get("/checkout").get_data(as_text=True)
    token = re.search(r'checkout_token[^>]*value="([^"]+)"', page).group(1)
    addr = default_address(get_user(email))
    return client.post("/checkout", data={"checkout_token": token, "address_choice": str(addr.id)})


def add(client, p, qty=1, size=None, color=None, engraving=None):
    data = {"quantity": qty}
    for k, v in (("size", size), ("color", color), ("engraving", engraving)):
        if v is not None:
            data[k] = v
    return client.post(f"/cart/add/{p.id}", data=data, headers=FETCH)


def opts(p):
    return p.size_list[0], p.color_list[0]


# ------------------------------------------------------------------ the product page

def test_watch_page_offers_size_colour_and_engraving(client):
    p = optioned_product()
    html = client.get(f"/shop/p/{p.slug}").get_data(as_text=True)
    assert html.count('name="size"') == len(p.size_list) and html.count('name="color"') == len(p.color_list)
    assert "Case size" in html and "Colour" in html and "data-engrave-toggle" in html
    assert f'maxlength="{p.engraving_max}"' in html


def test_a_watch_without_engraving_has_no_engraving_box(client):
    html = client.get("/shop/p/pulse-summit-rugged").get_data(as_text=True)
    assert "data-engrave-toggle" not in html and 'name="size"' in html


def test_product_cards_send_watches_to_the_product_page(client):
    html = client.get("/shop/c/dive-watches").get_data(as_text=True)
    assert "Choose options" in html and "#sizes" in html


# ------------------------------------------------------------------ validation

def test_size_and_colour_are_both_required(client):
    p = optioned_product()
    size, color = opts(p)
    r = add(client, p)
    assert r.status_code == 409 and "choose a size" in r.json["error"].lower()
    r = add(client, p, size=size)
    assert r.status_code == 409 and "choose a colour" in r.json["error"].lower()
    r = add(client, p, size="99 mm", color=color)
    assert r.status_code == 409 and "isn't available" in r.json["error"]
    r = add(client, p, size=size, color="Pink")
    assert r.status_code == 409
    r = add(client, p, size=size, color=color)
    assert r.json["ok"] and r.json["count"] == 1 and size in r.json["drawer"] and color in r.json["drawer"]


def test_engraving_rules(client):
    p = optioned_product()
    size, color = opts(p)
    assert add(client, p, size=size, color=color, engraving="x" * (p.engraving_max + 1)).status_code == 409
    assert add(client, p, size=size, color=color, engraving="<b>hi</b>").status_code == 409
    r = add(client, p, size=size, color=color, engraving="a|b")
    assert r.json["ok"] and "a b" in r.json["drawer"] and "a|b" not in r.json["drawer"]  # '|' is stripped, never stored
    gps = Product.query.filter_by(slug="pulse-summit-rugged").one()
    r = add(client, gps, size=gps.size_list[0], color=gps.color_list[0], engraving="Hello")
    assert r.status_code == 409 and "can't be engraved" in r.json["error"]
    r = add(client, p, size=size, color=color, engraving="J & M 2026")
    assert r.json["ok"] and "J &amp; M 2026" in r.json["drawer"]


def test_a_watch_with_no_options_ignores_stray_ones(client):
    p = in_stock_product()  # options switched off
    r = add(client, p, size="40 mm", color="Black")
    assert r.status_code == 409  # a choice that doesn't exist is refused, not silently dropped
    assert add(client, p).json["ok"]


# ------------------------------------------------------------------ the bag

def test_different_options_are_different_lines_sharing_stock(client):
    p = optioned_product()
    s0, c0 = opts(p)
    s1 = p.size_list[1] if len(p.size_list) > 1 else s0
    c1 = p.color_list[1] if len(p.color_list) > 1 else c0
    add(client, p, 2, s0, c0)
    add(client, p, 1, s1, c1)
    add(client, p, 1, s0, c0, engraving="MJ")
    html = client.get("/cart").get_data(as_text=True)
    assert c0 in html and c1 in html and "Engraved “MJ”" in html
    assert client.get("/cart/drawer").json["count"] == 4
    key = f"{s0}|{c0}|"
    client.post(f"/cart/update/{p.id}", data={"quantity": 5, "size": key}, headers=FETCH)
    assert client.get("/cart/drawer").json["count"] == 7
    client.post(f"/cart/remove/{p.id}", data={"size": key})
    assert client.get("/cart/drawer").json["count"] == 2
    p.stock = 3
    db.session.commit()
    add(client, p, 20, s0, c0)
    assert client.get("/cart/drawer").json["count"] <= 3  # stock is shared by every variant


def test_engraving_fee_is_added_by_the_server(customer):
    p = optioned_product()
    s0, c0 = opts(p)
    add(customer, p, 2, s0, c0, engraving="MJ")
    html = customer.get("/cart").get_data(as_text=True)
    from velora.money import fmt_minor
    each = p.price_minor + p.engraving_fee_minor
    assert fmt_minor(each) in html and fmt_minor(each * 2) in html
    r = _checkout(customer)
    assert r.status_code == 302
    o = Order.query.order_by(Order.id.desc()).first()
    item = OrderItem.query.filter_by(order_id=o.id).one()
    assert item.unit_price_minor == each and item.line_total_minor == each * 2 and o.subtotal_minor == each * 2
    assert item.size == f"{s0} · {c0} · Engraved “MJ”"


def test_the_price_comes_from_the_server_not_the_browser(customer):
    from velora.money import fmt_minor
    p = optioned_product()
    s0, c0 = opts(p)
    add(customer, p, 1, s0, c0)  # no engraving: no fee
    assert fmt_minor(p.price_minor + p.engraving_fee_minor) not in customer.get("/cart").get_data(as_text=True)
    customer.post(f"/cart/update/{p.id}", data={"quantity": 1, "size": f"{s0}|{c0}|", "unit_price": "1", "price": "1"}, headers=FETCH)
    html = customer.get("/cart").get_data(as_text=True)
    assert fmt_minor(p.price_minor) in html and fmt_minor(100) not in html  # a price sent by the browser is ignored


def test_guest_options_merge_into_the_account(client):
    p = optioned_product()
    s0, c0 = opts(p)
    add(client, p, 2, s0, c0, engraving="Hi")
    login(client, "buyer1@velora.example", "Buyer123!")
    u = get_user("buyer1@velora.example")
    item = CartItem.query.join(CartItem.cart).filter_by(user_id=u.id).one()
    assert item.size == f"{s0}|{c0}|Hi" and item.quantity == 2


def test_a_line_whose_option_was_removed_is_flagged(customer):
    p = optioned_product()
    s0, c0 = opts(p)
    add(customer, p, 1, s0, c0)
    p.colors = "Teal"  # the seller changed the colours after it was in the bag
    db.session.commit()
    html = customer.get("/cart").get_data(as_text=True)
    assert "isn&#39;t available" in html or "isn't available" in html
    page = customer.get("/checkout")
    assert page.status_code in (200, 302)


# ------------------------------------------------------------------ the order

def test_options_are_saved_on_the_order_and_shown_everywhere(customer):
    p = optioned_product()
    s0, c0 = opts(p)
    add(customer, p, 1, s0, c0, engraving="MJ")
    label = f"{s0} · {c0} · Engraved “MJ”"
    assert label in customer.get("/checkout").get_data(as_text=True)
    r = _checkout(customer)
    o = Order.query.order_by(Order.id.desc()).first()
    assert label in customer.get(r.headers["Location"]).get_data(as_text=True)
    assert label in customer.get(f"/account/orders/{o.number}").get_data(as_text=True)
    customer.post("/account/switch-profile")
    assert label in customer.get(f"/seller/orders/{o.number}").get_data(as_text=True)
    assert f"({label})" in customer.get("/seller/export/orders.csv").get_data(as_text=True)


# ------------------------------------------------------------------ the seller

def test_seller_edits_sizes_colours_and_engraving(seller):
    p = Product.query.filter_by(slug="panda-racing-42").one()
    data = {"name": p.name, "brand": p.brand, "category_id": p.category_id, "short_description": "x", "description": "y",
            "price": "11500", "stock": "10", "status": "active", "sizes": "38 mm, 42 mm ", "colors": "Steel, Black",
            "engraving_fee": "750", "engraving_max": "12"}
    assert seller.post(f"/seller/products/{p.id}", data=data).status_code == 302
    db.session.expire_all()
    p = db.session.get(Product, p.id)
    assert p.size_list == ["38 mm", "42 mm"] and p.color_list == ["Steel", "Black"]
    assert p.engraving_fee_minor == 75000 and p.engraving_max == 12
    off = seller.post(f"/seller/products/{p.id}", data={**data, "engraving_fee": ""})
    assert off.status_code == 302
    db.session.expire_all()
    assert db.session.get(Product, p.id).offers_engraving is False
    for bad in ({"colors": "A,A"}, {"sizes": "S,S"}, {"engraving_fee": "-5"}, {"engraving_max": "99"}):
        r = seller.post(f"/seller/products/{p.id}", data={**data, **bad})
        assert r.status_code == 200 and "field__error" in r.get_data(as_text=True), bad
    page = seller.get(f"/seller/products/{p.id}").get_data(as_text=True)
    assert 'name="colors"' in page and 'name="engraving_fee"' in page
