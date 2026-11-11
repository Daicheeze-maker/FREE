"""Cart, discount codes and checkout."""
import secrets

from flask import Blueprint, abort, flash, jsonify, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required

from ..extensions import db
from ..forms import CheckoutAddressForm, CheckoutForm, DiscountApplyForm
from ..models import Address, Order, Product
from ..services import cart as cart_service
from ..services.orders import CheckoutError, ShipTo, place_order
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
        cart_service.set_quantity(product, max(1, min(qty, cart_service.MAX_QTY_PER_LINE)),
                                  request.form.get("size", ""), add=True)
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
    size = request.form.get("size", "")
    try:
        final = cart_service.set_quantity(product, qty, size) if qty > 0 else cart_service.remove(product.id, size)
    except ValueError as exc:
        cart_service.remove(product.id, size)
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
    cart_service.remove(product_id, request.form.get("size", ""))
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


def _resolve_ship_to(addresses):
    """Work out the delivery address chosen on THIS checkout. Returns (ShipTo | None, choice, new_form, error).

    Nothing is assumed: the customer must pick one of their own saved addresses or type a new one.
    """
    choice = (request.form.get("address_choice") or "").strip()
    new_form = CheckoutAddressForm(formdata=request.form if choice == "new" else None, prefix="addr",
                                   full_name=current_user.full_name, phone=current_user.phone or "")
    if choice == "new":
        if new_form.validate():
            a = new_form
            parts = [a.line1.data, a.line2.data, a.city.data, a.region.data, a.postal_code.data, a.country.data]
            return ShipTo(a.full_name.data, a.phone.data, ", ".join(p for p in parts if p)), choice, new_form, None
        return None, choice, new_form, "Check the new address below."
    saved = {str(a.id): a for a in addresses}  # only this customer's own addresses are ever accepted
    if choice in saved:
        a = saved[choice]
        return ShipTo(a.full_name, a.phone, a.one_line()), choice, new_form, None
    return None, choice, new_form, "Choose where to deliver this order."


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
    addresses = Address.query.filter_by(user_id=current_user.id).order_by(Address.is_default.desc(), Address.id).all()
    form = CheckoutForm()
    choice, address_error = None, None
    new_form = CheckoutAddressForm(formdata=None, prefix="addr", full_name=current_user.full_name,
                                   phone=current_user.phone or "")
    if request.method == "GET":
        # One-time token: resubmitting this exact checkout can never create a second order.
        session["checkout_token"] = form.checkout_token.data = secrets.token_urlsafe(24)
        if not addresses:
            choice = "new"  # first purchase: the only option is to enter an address
    elif form.validate_on_submit():
        token = form.checkout_token.data
        prior = Order.query.filter_by(checkout_token=token, user_id=current_user.id).first()
        if prior:
            return redirect(url_for("shop.confirmation", number=prior.number))
        if token != session.get("checkout_token"):
            flash("This checkout has expired. Please review your order and submit again.", "error")
            return redirect(url_for("shop.checkout"))
        ship_to, choice, new_form, address_error = _resolve_ship_to(addresses)
        if ship_to is not None:
            try:
                order = place_order(current_user, DEMO_CREDIT, token, session.get("discount_code"),
                                    form.notes.data, ship_to)
            except CheckoutError as exc:
                flash(str(exc), "error")
                return redirect(url_for("shop.checkout") if cart_service.get_lines() else url_for("shop.cart"))
            if choice == "new" and new_form.save_address.data:
                if new_form.is_default.data or not addresses:
                    Address.query.filter_by(user_id=current_user.id).update({"is_default": False})
                addr = Address(user_id=current_user.id)
                new_form.populate_obj(addr)
                addr.is_default = bool(new_form.is_default.data or not addresses)
                db.session.add(addr)
                db.session.commit()
            session.pop("checkout_token", None)
            return redirect(url_for("shop.confirmation", number=order.number))
    totals = compute_totals(cart_service.subtotal_minor(lines), session.get("discount_code"), bool(lines))
    return render_template("shop/checkout.html", form=form, lines=lines, totals=totals, addresses=addresses,
                           choice=choice, new_form=new_form, address_error=address_error,
                           discount_form=DiscountApplyForm()), (400 if address_error else 200)


@bp.route("/checkout/confirmation/<number>")
@login_required
def confirmation(number):
    order = Order.query.filter_by(number=number).first_or_404()
    if order.user_id != current_user.id:
        abort(404)
    return render_template("shop/confirmation.html", order=order)
