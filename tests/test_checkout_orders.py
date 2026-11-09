import re

from velora.extensions import db
from velora.models import DiscountCode, Order, OrderStatus, PaymentRecord, Product
from velora.services.payments import DemoPaymentProvider, PaymentResult
from velora.services.pricing import compute_totals

from .conftest import get_user, in_stock_product, login


def _checkout(client):
    page = client.get("/checkout").get_data(as_text=True)
    token = re.search(r'name="checkout_token" type="hidden" value="([^"]+)"', page) or \
        re.search(r'id="checkout_token" name="checkout_token" type="hidden" value="([^"]+)"', page)
    token = token.group(1) if token else re.search(r'checkout_token[^>]*value="([^"]+)"', page).group(1)
    return token, client.post("/checkout", data={"checkout_token": token})


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
    r2 = customer.post("/checkout", data={"checkout_token": token})
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


def test_demo_credit_is_unlimited_and_ships_immediately(customer):
    p = in_stock_product()
    p.price_minor = 999_999_999_00
    db.session.commit()
    customer.post(f"/cart/add/{p.id}", data={"quantity": 1})
    _checkout(customer)
    o = Order.query.order_by(Order.id.desc()).first()
    assert o.total_minor >= p.price_minor
    assert o.status == OrderStatus.SHIPPED and o.payment.status == "succeeded"
    assert o.payment.method == "demo_credit"


def test_checkout_page_offers_no_payment_outcomes(customer):
    customer.post(f"/cart/add/{in_stock_product().id}", data={"quantity": 1})
    page = customer.get("/checkout").get_data(as_text=True)
    assert "Unlimited" in page
    assert 'name="payment_method"' not in page
    assert 'name="address_id"' not in page


def test_new_account_checks_out_without_an_address(client):
    assert login(client, "no.address@example.com", "x").status_code == 302
    client.post(f"/cart/add/{in_stock_product().id}", data={"quantity": 1})
    _, r = _checkout(client)
    assert r.status_code == 302 and "/checkout/confirmation/" in r.headers["Location"]
    assert "Delivery is on the way, wait 10 mins po." in client.get(r.headers["Location"]).get_data(as_text=True)
    u = get_user("no.address@example.com")
    assert Order.query.filter_by(user_id=u.id).one().ship_address


def test_checkout_validation(customer):
    p = in_stock_product()
    customer.post(f"/cart/add/{p.id}", data={"quantity": 1})
    count = Order.query.count()
    page = customer.get("/checkout").get_data(as_text=True)
    token = re.search(r'checkout_token[^>]*value="([^"]+)"', page).group(1)
    r = customer.post("/checkout", data={"checkout_token": token + "-stale"})
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
    other_order = Order.query.filter(Order.user.has(email="jonah@example.com")).first()
    c = app.test_client()
    login(c, "customer@velora.example", "Customer123!")
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
    u = get_user("customer@velora.example")
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
