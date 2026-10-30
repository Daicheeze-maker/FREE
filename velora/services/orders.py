"""Checkout, order creation and order-status workflow."""
import secrets

from flask import url_for
from sqlalchemy import update

from ..extensions import db
from ..models import (PRODUCT_ACTIVE, DiscountCode, Notification, Order, OrderItem, OrderStatus,
                      PaymentRecord, Product, utcnow)
from ..money import fmt_minor
from . import cart as cart_service
from .payments import get_provider
from .pricing import DiscountError, compute_totals, find_discount, validate_discount


class CheckoutError(Exception):
    pass


def new_order_number():
    while True:
        number = "VM-" + utcnow().strftime("%y%m") + "-" + secrets.token_hex(3).upper()
        if not Order.query.filter_by(number=number).first():
            return number


def notify(user_id, title, body="", link=None, icon="bell"):
    db.session.add(Notification(user_id=user_id, title=title, body=body, link=link, icon=icon))


def place_order(user, address, payment_method, checkout_token, discount_code=None, notes=None):
    """Create an order atomically. Everything is recomputed from the database.

    Idempotent per checkout_token: resubmitting the same checkout returns the existing order.
    """
    existing = Order.query.filter_by(checkout_token=checkout_token).first()
    if existing:
        if existing.user_id != user.id:
            raise CheckoutError("Invalid checkout session.")
        return existing

    provider = get_provider()
    if payment_method not in provider.methods:
        raise CheckoutError("Choose a valid payment method.")
    if address is None or address.user_id != user.id:
        raise CheckoutError("Choose a delivery address.")

    lines = cart_service.get_lines()
    if not lines:
        raise CheckoutError("Your bag is empty.")
    for line in lines:
        if line.problem:
            raise CheckoutError(f"{line.product.name}: {line.problem}. Update your bag to continue.")

    subtotal = sum(l.line_total_minor for l in lines)
    discount = None
    if discount_code:
        try:
            discount = validate_discount(find_discount(discount_code), subtotal)
        except DiscountError as exc:
            raise CheckoutError(str(exc))
    totals = compute_totals(subtotal, discount.code if discount else None)

    order = Order(
        number=new_order_number(), user_id=user.id, checkout_token=checkout_token, currency="PHP",
        subtotal_minor=totals.subtotal_minor, discount_minor=totals.discount_minor,
        shipping_minor=totals.shipping_minor, total_minor=totals.total_minor,
        discount_code=discount.code if discount else None,
        ship_name=address.full_name, ship_phone=address.phone, ship_address=address.one_line(),
        notes=(notes or "").strip()[:500] or None,
    )
    # Spread the order discount across lines proportionally (for accurate per-item snapshots)
    remaining = totals.discount_minor
    try:
        for idx, line in enumerate(lines):
            p = line.product
            # Atomic conditional decrement: fails if another checkout took the stock first
            result = db.session.execute(
                update(Product)
                .where(Product.id == p.id, Product.stock >= line.quantity, Product.status == PRODUCT_ACTIVE)
                .values(stock=Product.stock - line.quantity, sold_count=Product.sold_count + line.quantity)
            )
            if result.rowcount != 1:
                raise CheckoutError(f"Sorry — {p.name} just sold out or changed. Please review your bag.")
            if idx == len(lines) - 1:
                share = remaining
            else:
                share = (totals.discount_minor * line.line_total_minor) // subtotal if subtotal else 0
                remaining -= share
            img = p.primary_image
            order.items.append(OrderItem(
                product_id=p.id, product_name=p.name, product_sku=p.sku, product_brand=p.brand,
                image_url=(img.url if img and img.url else (url_for("main.media", filename=img.filename) if img and img.filename else None)),
                unit_price_minor=p.price_minor, quantity=line.quantity, discount_minor=share,
                line_total_minor=line.line_total_minor - share,
            ))
        if discount:
            # Atomic usage counter respecting max_uses
            cond = [DiscountCode.id == discount.id]
            if discount.max_uses is not None:
                cond.append(DiscountCode.used_count < DiscountCode.max_uses)
            res = db.session.execute(update(DiscountCode).where(*cond).values(used_count=DiscountCode.used_count + 1))
            if res.rowcount != 1:
                raise CheckoutError("That discount code has just reached its usage limit.")

        result = provider.charge(order.total_minor, order.currency, payment_method, order.number)
        if result.status == "failed":
            raise CheckoutError(result.message)
        order.payments.append(PaymentRecord(
            provider=provider.name, method=payment_method, status=result.status,
            amount_minor=order.total_minor, currency=order.currency, reference=result.reference,
            message=result.message,
        ))
        if result.status == "succeeded":
            order.status = OrderStatus.CONFIRMED
            order.confirmed_at = utcnow()
        db.session.add(order)
        db.session.flush()
        notify(user.id, f"Order {order.number} received",
               f"Total {fmt_minor(order.total_minor)} · {'payment confirmed (demo)' if result.status == 'succeeded' else 'pay on delivery'}",
               url_for("account.order_detail", number=order.number), icon="package-check")
        cart_service.clear()
        db.session.commit()
    except CheckoutError:
        db.session.rollback()
        raise
    except Exception:
        db.session.rollback()
        # A concurrent duplicate submit with the same token loses the unique-constraint race
        dup = Order.query.filter_by(checkout_token=checkout_token, user_id=user.id).first()
        if dup:
            return dup
        raise
    return order


STATUS_MESSAGES = {
    OrderStatus.CONFIRMED: ("confirmed", "We've confirmed your order and are getting it ready.", "badge-check"),
    OrderStatus.PROCESSING: ("being packed", "Your items are being carefully packed.", "package"),
    OrderStatus.SHIPPED: ("on its way", "Your order has left our studio.", "truck"),
    OrderStatus.DELIVERED: ("delivered", "Enjoy! You can now review the items you bought.", "home"),
    OrderStatus.CANCELLED: ("cancelled", "Your order was cancelled and any stock was released.", "circle-x"),
}


def change_status(order, new_status, reason=None):
    """Apply a validated status transition. Restocks on cancellation. Caller commits."""
    if new_status not in OrderStatus.ALL:
        raise ValueError("Unknown status")
    if not OrderStatus.can_transition(order.status, new_status):
        raise ValueError(f"Cannot change an order from {order.status} to {new_status}.")
    now = utcnow()
    order.status = new_status
    if new_status == OrderStatus.CONFIRMED:
        order.confirmed_at = now
    elif new_status == OrderStatus.SHIPPED:
        order.shipped_at = now
    elif new_status == OrderStatus.DELIVERED:
        order.delivered_at = now
        pay = order.payment
        if pay and pay.method == "cod" and pay.status == "pending":
            pay.status = "succeeded"
            pay.message = "Collected on delivery (demo)."
    elif new_status == OrderStatus.CANCELLED:
        order.cancelled_at = now
        order.cancel_reason = (reason or "")[:300] or None
        for item in order.items:
            if item.product_id:
                db.session.execute(update(Product).where(Product.id == item.product_id).values(
                    stock=Product.stock + item.quantity,
                    sold_count=db.case((Product.sold_count >= item.quantity, Product.sold_count - item.quantity), else_=0)))
        pay = order.payment
        if pay and pay.status == "succeeded":
            pay.status = "refunded"
            pay.message = "Simulated refund issued (demo)."
    word, body, icon = STATUS_MESSAGES[new_status]
    notify(order.user_id, f"Order {order.number} is {word}", body,
           url_for("account.order_detail", number=order.number), icon=icon)
