import re

from velora.extensions import db
from velora.models import DiscountCode, Order, OrderStatus, PaymentRecord, Product
from velora.services.payments import DemoPaymentProvider, PaymentResult
from velora.services.pricing import compute_totals

from .conftest import default_address, get_user, in_stock_product, login


def _token(client):
    page = client.get("/checkout").get_data(as_text=True)
    return re.search(r'checkout_token[^>]*value="([^"]+)"', page).group(1)


NEW_ADDRESS = {"address_choice": "new", "addr-label": "Work", "addr-full_name": "Maya Santos",
               "addr-phone": "+63 917 555 0199", "addr-line1": "88 Ayala Ave", "addr-city": "Makati",
               "addr-region": "Metro Manila", "addr-postal_code": "1226", "addr-country": "Philippines"}


def _checkout(client, address=None, **extra):
    """Place an order the way a shopper must: by choosing a saved address (default: their default one)."""
    token = _token(client)
    if address is None:
        u = get_user("buyer1@velora.example")
        address = {"address_choice": str(default_address(u).id)}
    return token, client.post("/checkout", data={"checkout_token": token, **address, **extra})


def test_checkout_creates_order_and_deducts_stock(customer):
    p = in_stock_product()
    before = p.stock
    customer.post(f"/cart/add/{p.id}", data={"quantity": 2})
    _, r = _checkout(customer)
    assert r.status_code == 302 and "/checkout/confirmation/" in r.headers["Location"]
    db.session.refresh(p)
    assert p.stock == before - 2
    order = Order.query.order_by(Order.id.desc()).first()
    assert order.status == OrderStatus.SHIPPED and order.confirmed_at and order.shipped_at
    assert order.items[0].product_name == p.name and order.items[0].unit_price_minor == p.price_minor
    assert order.payment.status == "succeeded" and order.payment.reference.startswith("DEMO-")
    assert customer.get("/cart", headers={"X-Requested-With": "fetch"}).status_code == 200
    assert customer.get("/cart/drawer").json["count"] == 0


def test_order_snapshot_survives_catalog_change(customer):
    p = in_stock_product()
    customer.post(f"/cart/add/{p.id}", data={"quantity": 1})
    _checkout(customer)
    order = Order.query.order_by(Order.id.desc()).first()
    original = (order.items[0].product_name, order.items[0].unit_price_minor)
    p.name, p.price_minor = "Renamed", 1
    db.session.commit()
    db.session.refresh(order)
    assert (order.items[0].product_name, order.items[0].unit_price_minor) == original


def test_duplicate_checkout_submission_creates_one_order(customer):
    p = in_stock_product()
    customer.post(f"/cart/add/{p.id}", data={"quantity": 1})
    count = Order.query.count()
    token, r1 = _checkout(customer)
    r2 = customer.post("/checkout", data={"checkout_token": token, "address_choice": str(default_address(get_user("buyer1@velora.example")).id)})
    assert Order.query.count() == count + 1
    assert r1.headers["Location"] == r2.headers["Location"]


def test_checkout_rechecks_inventory(customer):
    p = in_stock_product()
    customer.post(f"/cart/add/{p.id}", data={"quantity": 3})
    p.stock = 1  # someone else bought it meanwhile
    db.session.commit()
    count = Order.query.count()
    _, r = _checkout(customer)
    assert Order.query.count() == count
    db.session.refresh(p)
    assert p.stock == 1


def test_failed_payment_rolls_back(customer, monkeypatch):
    monkeypatch.setattr(DemoPaymentProvider, "charge", lambda *a: PaymentResult("failed", "DEMO-X", "Nope."))
    p = in_stock_product()
    before = p.stock
    customer.post(f"/cart/add/{p.id}", data={"quantity": 1})
    count = Order.query.count()
    _, r = _checkout(customer)
    assert Order.query.count() == count
    db.session.refresh(p)
    assert p.stock == before
    assert customer.get("/cart/drawer").json["count"] == 1  # bag kept


def test_buyer_starts_with_500k_and_it_is_spent_at_checkout(customer):
    u = get_user("buyer1@velora.example")
    assert u.balance_minor == 50_000_000  # PHP 500,000.00
    p = in_stock_product()
    customer.post(f"/cart/add/{p.id}", data={"quantity": 1})
    _checkout(customer)
    o = Order.query.order_by(Order.id.desc()).first()
    db.session.expire_all()
    assert o.status == OrderStatus.SHIPPED and o.payment.status == "succeeded" and o.payment.method == "demo_credit"
    assert get_user("buyer1@velora.example").balance_minor == 50_000_000 - o.total_minor


def test_cannot_spend_more_than_the_500k_credit(customer):
    p = in_stock_product()
    p.price_minor = 60_000_000  # PHP 600,000 > the buyer's PHP 500,000
    stock = p.stock
    db.session.commit()
    customer.post(f"/cart/add/{p.id}", data={"quantity": 1})
    count = Order.query.count()
    _, r = _checkout(customer)
    assert r.status_code == 302 and r.headers["Location"].endswith("/checkout")
    assert Order.query.count() == count
    db.session.expire_all()
    assert get_user("buyer1@velora.example").balance_minor == 50_000_000  # untouched
    assert db.session.get(Product, p.id).stock == stock  # stock released with the rolled-back order
    assert "Not enough demo credit" in customer.get("/checkout").get_data(as_text=True)  # the flashed message


def test_credit_runs_out_across_several_orders_and_never_goes_negative(customer):
    p = in_stock_product()
    p.price_minor = 30_000_000  # PHP 300,000 each
    db.session.commit()
    customer.post(f"/cart/add/{p.id}", data={"quantity": 1})
    _, first = _checkout(customer)
    assert "/checkout/confirmation/" in first.headers["Location"]
    customer.post(f"/cart/add/{p.id}", data={"quantity": 1})
    _, second = _checkout(customer)  # only about PHP 200,000 left
    assert second.headers["Location"].endswith("/checkout")
    db.session.expire_all()
    assert 0 <= get_user("buyer1@velora.example").balance_minor < 30_000_000
    assert Order.query.filter_by(user_id=get_user("buyer1@velora.example").id).count() >= 1


def test_checkout_page_shows_credit_and_blocks_an_unaffordable_order(customer):
    p = in_stock_product()
    customer.post(f"/cart/add/{p.id}", data={"quantity": 1})
    html = customer.get("/checkout").get_data(as_text=True)
    assert "Your demo credit" in html and "₱500,000.00" in html and "Left after paying" in html
    p.price_minor = 60_000_000
    db.session.commit()
    html = customer.get("/checkout").get_data(as_text=True)
    assert "more than your credit" in html and "disabled" in html


def test_cancelling_refunds_the_credit(customer):
    p = in_stock_product()
    customer.post(f"/cart/add/{p.id}", data={"quantity": 1})
    _checkout(customer)
    o = Order.query.order_by(Order.id.desc()).first()
    o.status = OrderStatus.CONFIRMED  # a cancellable stage (this demo ships paid orders immediately)
    db.session.commit()
    db.session.expire_all()
    assert get_user("buyer1@velora.example").balance_minor < 50_000_000
    assert customer.post(f"/account/orders/{o.number}/cancel", data={}).status_code == 302
    db.session.expire_all()
    assert get_user("buyer1@velora.example").balance_minor == 50_000_000
    assert Order.query.get(o.id).payment.status == "refunded"


def test_admin_can_reset_a_buyers_credit(app):
    from velora.models import User
    c = app.test_client()
    login(c, "admin@velora.example", "Admin123!")
    u = get_user("buyer2@velora.example")
    u.balance_minor = 1234
    db.session.commit()
    assert c.post(f"/admin/users/{u.id}/reset-credit").status_code == 302
    db.session.expire_all()
    assert User.query.get(u.id).balance_minor == 50_000_000


def test_checkout_page_offers_no_payment_outcomes(customer):
    customer.post(f"/cart/add/{in_stock_product().id}", data={"quantity": 1})
    page = customer.get("/checkout").get_data(as_text=True)
    assert "Your demo credit" in page
    assert 'name="payment_method"' not in page
    assert 'name="address_id"' not in page


def test_checkout_asks_for_an_address_every_time(customer):
    customer.post(f"/cart/add/{in_stock_product().id}", data={"quantity": 1})
    html = customer.get("/checkout").get_data(as_text=True)
    assert "Where should we deliver this order?" in html
    assert 'name="address_choice"' in html and "Deliver to a new address" in html
    assert "checked" not in html.split('name="address_choice"')[1].split(">")[0]  # nothing pre-selected
    for a in get_user("buyer1@velora.example").addresses:  # every saved address is offered
        assert a.line1 in html


def test_cannot_order_without_choosing_an_address(customer):
    customer.post(f"/cart/add/{in_stock_product().id}", data={"quantity": 1})
    count = Order.query.count()
    token = _token(customer)
    r = customer.post("/checkout", data={"checkout_token": token})
    assert r.status_code == 400 and "Choose where to deliver this order" in r.get_data(as_text=True)
    assert Order.query.count() == count
    assert customer.get("/cart/drawer").json["count"] == 1  # bag untouched


def test_order_uses_the_chosen_saved_address(customer):
    u = get_user("buyer1@velora.example")
    other = next(a for a in u.addresses if not a.is_default)  # e.g. "Office", not the default
    customer.post(f"/cart/add/{in_stock_product().id}", data={"quantity": 1})
    _, r = _checkout(customer, {"address_choice": str(other.id)})
    assert r.status_code == 302
    o = Order.query.order_by(Order.id.desc()).first()
    assert o.ship_address == other.one_line() and o.ship_phone == other.phone
    assert other.one_line() in customer.get(r.headers["Location"]).get_data(as_text=True)


def test_new_address_is_used_and_saved(customer):
    u = get_user("buyer1@velora.example")
    before = len(u.addresses)
    customer.post(f"/cart/add/{in_stock_product().id}", data={"quantity": 1})
    _, r = _checkout(customer, NEW_ADDRESS, **{"addr-save_address": "y"})
    assert r.status_code == 302
    o = Order.query.order_by(Order.id.desc()).first()
    assert "88 Ayala Ave" in o.ship_address and "Makati" in o.ship_address
    db.session.expire_all()
    assert len(get_user("buyer1@velora.example").addresses) == before + 1


def test_new_address_not_saved_when_unticked(customer):
    u = get_user("buyer1@velora.example")
    before = len(u.addresses)
    customer.post(f"/cart/add/{in_stock_product().id}", data={"quantity": 1})
    _, r = _checkout(customer, NEW_ADDRESS)  # save box not sent = unticked
    assert r.status_code == 302
    db.session.expire_all()
    assert len(get_user("buyer1@velora.example").addresses) == before
    assert "88 Ayala Ave" in Order.query.order_by(Order.id.desc()).first().ship_address


def test_invalid_new_address_is_rejected(customer):
    customer.post(f"/cart/add/{in_stock_product().id}", data={"quantity": 1})
    count = Order.query.count()
    bad = {**NEW_ADDRESS, "addr-line1": "", "addr-phone": "abc"}
    _, r = _checkout(customer, bad)
    assert r.status_code == 400 and "field__error" in r.get_data(as_text=True)
    assert Order.query.count() == count


def test_cannot_ship_to_another_customers_address(customer):
    other = default_address(get_user("buyer2@velora.example"))
    customer.post(f"/cart/add/{in_stock_product().id}", data={"quantity": 1})
    count = Order.query.count()
    _, r = _checkout(customer, {"address_choice": str(other.id)})
    assert r.status_code == 400 and Order.query.count() == count


def test_first_purchase_with_no_saved_address_must_enter_one(client):
    assert login(client, "no.address@example.com", "x").status_code == 302
    client.post(f"/cart/add/{in_stock_product().id}", data={"quantity": 1})
    html = client.get("/checkout").get_data(as_text=True)
    assert 'value="new" id="addr-choice-new" checked' in html  # the only option is pre-chosen
    token = _token(client)
    assert client.post("/checkout", data={"checkout_token": token}).status_code == 400
    r = client.post("/checkout", data={"checkout_token": token, **NEW_ADDRESS, "addr-save_address": "y"})
    assert r.status_code == 302 and "/checkout/confirmation/" in r.headers["Location"]
    assert "Delivery is on the way, wait 10 mins po." in client.get(r.headers["Location"]).get_data(as_text=True)
    u = get_user("no.address@example.com")
    assert len(u.addresses) == 1 and u.addresses[0].is_default  # saved, and becomes the default


def test_checkout_validation(customer):
    p = in_stock_product()
    customer.post(f"/cart/add/{p.id}", data={"quantity": 1})
    count = Order.query.count()
    page = customer.get("/checkout").get_data(as_text=True)
    token = re.search(r'checkout_token[^>]*value="([^"]+)"', page).group(1)
    r = customer.post("/checkout", data={"checkout_token": token + "-stale", "address_choice": "1"})
    assert r.status_code == 302 and r.headers["Location"].endswith("/checkout")
    assert Order.query.count() == count


def test_browser_submitted_prices_are_ignored(customer):
    p = in_stock_product()
    customer.post(f"/cart/add/{p.id}", data={"quantity": 1, "price": "0.01", "total": "1"})
    _checkout(customer)
    o = Order.query.order_by(Order.id.desc()).first()
    assert o.subtotal_minor == p.price_minor


def test_staff_cannot_checkout(seller):
    assert seller.get("/checkout").status_code == 302


# ---------------------------------------------------------------- discounts

def test_discount_percent_and_minimum(app):
    t = compute_totals(100000, "WELCOME10")
    assert t.discount_minor == 10000
    t = compute_totals(100000, "STYLE500")  # min ₱5,000
    assert t.discount_minor == 0
    t = compute_totals(600000, "STYLE500")
    assert t.discount_minor == 50000


def test_expired_and_exhausted_codes(customer):
    p = in_stock_product()
    customer.post(f"/cart/add/{p.id}", data={"quantity": 1})
    customer.post("/cart/discount", data={"code": "SUMMER25"})
    assert customer.get("/cart").get_data(as_text=True).count("SUMMER25") == 0
    d = DiscountCode.query.filter_by(code="SEASON15").first()
    d.used_count = d.max_uses
    db.session.commit()
    r = customer.post("/cart/discount", data={"code": "SEASON15"}, follow_redirects=True)
    assert "usage limit" in r.get_data(as_text=True)


def test_discount_applied_in_order_and_usage_counted(customer):
    p = Product.query.filter_by(name="Minimalist Leather Strap Watch").first()
    customer.post(f"/cart/add/{p.id}", data={"quantity": 1})
    customer.post("/cart/discount", data={"code": "welcome10"})
    _checkout(customer)
    o = Order.query.order_by(Order.id.desc()).first()
    assert o.discount_code == "WELCOME10"
    assert o.discount_minor == p.price_minor // 10
    assert sum(i.discount_minor for i in o.items) == o.discount_minor
    assert o.total_minor == o.subtotal_minor - o.discount_minor + o.shipping_minor
    assert DiscountCode.query.filter_by(code="WELCOME10").first().used_count == 1


def test_free_shipping_threshold(app):
    assert compute_totals(100000).shipping_minor == 15000
    assert compute_totals(300000).shipping_minor == 0


# ----------------------------------------------------------- orders/rules

def test_order_ownership(app):
    other_order = Order.query.filter(Order.user.has(email="buyer2@velora.example")).first()
    c = app.test_client()
    login(c, "buyer1@velora.example", "Buyer123!")
    assert c.get(f"/account/orders/{other_order.number}").status_code == 404
    assert c.post(f"/account/orders/{other_order.number}/cancel").status_code == 404
    db.session.refresh(other_order)
    assert other_order.status != OrderStatus.CANCELLED


def test_customer_cancel_rules_and_restock(customer):
    p = in_stock_product()
    customer.post(f"/cart/add/{p.id}", data={"quantity": 2})
    _checkout(customer)
    o = Order.query.order_by(Order.id.desc()).first()
    o.status = OrderStatus.CONFIRMED  # new orders ship immediately; cancelling needs an earlier status
    db.session.commit()
    db.session.refresh(p)
    stock_after_order = p.stock
    r = customer.post(f"/account/orders/{o.number}/cancel", data={"reason": "test"})
    assert r.status_code == 302
    db.session.refresh(o)
    db.session.refresh(p)
    assert o.status == OrderStatus.CANCELLED and p.stock == stock_after_order + 2
    assert PaymentRecord.query.filter_by(order_id=o.id).first().status == "refunded"


def test_customer_cannot_cancel_shipped(customer):
    u = get_user("buyer1@velora.example")
    o = Order.query.filter_by(user_id=u.id, status=OrderStatus.SHIPPED).first() or \
        Order.query.filter_by(user_id=u.id, status=OrderStatus.DELIVERED).first()
    customer.post(f"/account/orders/{o.number}/cancel", data={})
    db.session.refresh(o)
    assert o.status != OrderStatus.CANCELLED


def test_seller_status_transitions_enforced(seller):
    o = Order.query.filter_by(status=OrderStatus.PENDING).first()
    seller.post(f"/seller/orders/{o.number}", data={"status": "delivered"})
    db.session.refresh(o)
    assert o.status == OrderStatus.PENDING  # invalid jump rejected
    seller.post(f"/seller/orders/{o.number}", data={"status": "confirmed"})
    db.session.refresh(o)
    assert o.status == OrderStatus.CONFIRMED and o.confirmed_at
    assert any("confirmed" in n.title for n in o.user.notifications)


def test_order_status_model_rules():
    assert OrderStatus.can_transition("pending", "confirmed")
    assert not OrderStatus.can_transition("delivered", "cancelled")
    assert not OrderStatus.can_transition("shipped", "pending")


def test_new_address_form_keeps_name_and_phone_prefill_after_an_error(client):
    assert login(client, "no.address@example.com", "x").status_code == 302
    client.post(f"/cart/add/{in_stock_product().id}", data={"quantity": 1})
    token = _token(client)
    html = client.post("/checkout", data={"checkout_token": token}).get_data(as_text=True)  # nothing chosen
    assert "Choose where to deliver this order" in html
    assert 'name="addr-full_name"' in html
    name = get_user("no.address@example.com").full_name
    assert f'value="{name}"' in html
