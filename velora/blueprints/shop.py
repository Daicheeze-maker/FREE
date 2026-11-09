"""Cart, discount codes and checkout."""
import secrets

from flask import Blueprint, abort, flash, jsonify, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required

from ..extensions import db
from ..forms import CheckoutForm, DiscountApplyForm
from ..models import Order, Product
from ..services import cart as cart_service
from ..services.orders import CheckoutError, place_order
from ..services.payments import DEMO_CREDIT
from ..services.pricing import DiscountError, compute_totals, find_discount, validate_discount

bp = Blueprint("shop", __name__)


def _is_fetch():
    return request.headers.get("X-Requested-With") == "fetch"


def _cart_payload(message=None, ok=True, status=200):
    from flask import g
    from ..services.currency import PriceDisplay
    g.money = g.get("money") or PriceDisplay()
    lines = cart_service.get_lines()
    totals = compute_totals(cart_service.subtotal_minor(lines), session.get("discount_code"), bool(lines))
    drawer = render_template("shop/_drawer_body.html", lines=lines, totals=totals, money=g.money)
    return jsonify(ok=ok, message=message, count=sum(l.quantity for l in lines), drawer=drawer,
                   subtotal=g.money(totals.subtotal_minor)), status


def _require_customer_or_guest():
    if current_user.is_authenticated and current_user.role != "customer":
        msg = "Staff accounts can't shop. Sign in with a customer account to place orders."
        if _is_fetch():
            return jsonify(ok=False, error=msg), 403
        flash(msg, "info")
        return redirect(request.referrer or url_for("main.home"))
    return None


@bp.route("/cart")
def cart():
    lines = cart_service.get_lines()
    totals = compute_totals(cart_service.subtotal_minor(lines), session.get("discount_code"), bool(lines))
    if session.get("discount_code") and not totals.discount:
        session.pop("discount_code", None)
    return render_template("shop/cart.html", lines=lines, totals=totals, discount_form=DiscountApplyForm())


@bp.get("/cart/drawer")
def drawer():
    return _cart_payload()


@bp.post("/cart/add/<int:product_id>")
def add(product_id):
    blocked = _require_customer_or_guest()
    if blocked:
        return blocked
    product = db.session.get(Product, product_id) or abort(404)
    qty = request.form.get("quantity", 1, type=int) or 1
    try:
        cart_service.set_quantity(product, max(1, min(qty, cart_service.MAX_QTY_PER_LINE)), add=True)
    except ValueError as exc:
        if _is_fetch():
            return jsonify(ok=False, error=str(exc)), 409
        flash(str(exc), "error")
        return redirect(request.referrer or url_for("catalog.detail", slug=product.slug))
    if _is_fetch():
        return _cart_payload(f"Added {product.name} to your bag")
    flash(f"Added {product.name} to your bag.", "success")
    return redirect(url_for("shop.cart"))


@bp.post("/cart/update/<int:product_id>")
def update(product_id):
    blocked = _require_customer_or_guest()
    if blocked:
        return blocked
    product = db.session.get(Product, product_id) or abort(404)
    qty = request.form.get("quantity", type=int)
    if qty is None or qty < 0:
        msg = "Enter a valid quantity."
        if _is_fetch():
            return jsonify(ok=False, error=msg), 400
        flash(msg, "error")
        return redirect(url_for("shop.cart"))
    try:
        final = cart_service.set_quantity(product, qty) if qty > 0 else cart_service.remove(product.id)
    except ValueError as exc:
        cart_service.remove(product.id)
        final, msg = 0, str(exc)
    else:
        msg = None
        if qty > 0 and final < qty:
            msg = f"Only {final} of {product.name} available — quantity adjusted."
    if _is_fetch():
        return _cart_payload(msg)
    if msg:
        flash(msg, "info")
    return redirect(url_for("shop.cart"))


@bp.post("/cart/remove/<int:product_id>")
def remove(product_id):
    cart_service.remove(product_id)
    if _is_fetch():
        return _cart_payload("Removed from your bag")
    flash("Removed from your bag.", "info")
    return redirect(url_for("shop.cart"))


@bp.post("/cart/discount")
def apply_discount():
    form = DiscountApplyForm()
    if request.form.get("action") == "remove":
        session.pop("discount_code", None)
        flash("Discount removed.", "info")
        return redirect(request.form.get("back") == "checkout" and url_for("shop.checkout") or url_for("shop.cart"))
    if form.validate_on_submit():
        try:
            discount = validate_discount(find_discount(form.code.data), cart_service.subtotal_minor())
        except DiscountError as exc:
            flash(str(exc), "error")
        else:
            session["discount_code"] = discount.code
            flash(f"Code {discount.code} applied.", "success")
    else:
        flash("Enter a discount code.", "error")
    return redirect(request.form.get("back") == "checkout" and url_for("shop.checkout") or url_for("shop.cart"))


@bp.route("/checkout", methods=["GET", "POST"])
@login_required
def checkout():
    if current_user.role != "customer":
        flash("Checkout is available to customer accounts.", "info")
        return redirect(url_for("shop.cart"))
    lines = cart_service.get_lines()
    if not lines and request.method == "GET":
        flash("Your bag is empty.", "info")
        return redirect(url_for("shop.cart"))
    form = CheckoutForm()
    if request.method == "GET":
        # One-time token: resubmitting this exact checkout can never create a second order.
        session["checkout_token"] = form.checkout_token.data = secrets.token_urlsafe(24)
    elif form.validate_on_submit():
        token = form.checkout_token.data
        prior = Order.query.filter_by(checkout_token=token, user_id=current_user.id).first()
        if prior:
            return redirect(url_for("shop.confirmation", number=prior.number))
        if token != session.get("checkout_token"):
            flash("This checkout has expired. Please review your order and submit again.", "error")
            return redirect(url_for("shop.checkout"))
        try:
            order = place_order(current_user, DEMO_CREDIT, token, session.get("discount_code"), form.notes.data)
        except CheckoutError as exc:
            flash(str(exc), "error")
            return redirect(url_for("shop.checkout") if cart_service.get_lines() else url_for("shop.cart"))
        session.pop("checkout_token", None)
        return redirect(url_for("shop.confirmation", number=order.number))
    totals = compute_totals(cart_service.subtotal_minor(lines), session.get("discount_code"), bool(lines))
    return render_template("shop/checkout.html", form=form, lines=lines, totals=totals,
                           discount_form=DiscountApplyForm())


@bp.route("/checkout/confirmation/<number>")
@login_required
def confirmation(number):
    order = Order.query.filter_by(number=number).first_or_404()
    if order.user_id != current_user.id:
        abort(404)
    return render_template("shop/confirmation.html", order=order)
