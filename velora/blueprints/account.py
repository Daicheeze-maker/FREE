"""Customer account area."""
from flask import Blueprint, abort, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy.exc import IntegrityError

from ..extensions import db
from ..forms import AddressForm, CancelOrderForm, PasswordChangeForm, ProfileForm
from ..models import (PRODUCT_ACTIVE, Address, Notification, Order, OrderStatus, Product, ProductReview,
                      WishlistItem)
from ..security import roles_required
from ..services.orders import change_status
from .main import recently_viewed

bp = Blueprint("account", __name__, url_prefix="/account")
customer_only = roles_required("customer")


def _own_order(number):
    order = Order.query.filter_by(number=number).first()
    # 404 (not 403) so order numbers belonging to others aren't confirmed to exist
    if order is None or order.user_id != current_user.id:
        abort(404)
    return order


@bp.route("/")
@customer_only
def dashboard():
    orders = Order.query.filter_by(user_id=current_user.id).order_by(Order.created_at.desc()).all()
    active = [o for o in orders if o.status not in (OrderStatus.DELIVERED, OrderStatus.CANCELLED)]
    spent = sum(o.total_minor for o in orders if o.status != OrderStatus.CANCELLED)
    notes = Notification.query.filter_by(user_id=current_user.id).order_by(Notification.created_at.desc()).limit(5).all()
    wish = WishlistItem.query.filter_by(user_id=current_user.id).order_by(WishlistItem.created_at.desc()).limit(4).all()
    reviewed = {r.product_id for r in ProductReview.query.filter_by(user_id=current_user.id)}
    to_review = []
    for o in orders:
        if o.status == OrderStatus.DELIVERED:
            for it in o.items:
                if it.product and it.product_id not in reviewed and it.product.status == PRODUCT_ACTIVE and it.product not in to_review:
                    to_review.append(it.product)
    return render_template("account/dashboard.html", orders=orders[:4], active=active, spent=spent,
                           order_count=len(orders), notes=notes, wish=wish, to_review=to_review[:3],
                           recent=recently_viewed(limit=4))


@bp.route("/orders")
@customer_only
def orders():
    status = request.args.get("status")
    q = Order.query.filter_by(user_id=current_user.id)
    if status in OrderStatus.ALL:
        q = q.filter_by(status=status)
    return render_template("account/orders.html", orders=q.order_by(Order.created_at.desc()).all(),
                           status=status, statuses=OrderStatus.ALL)


@bp.route("/orders/<number>")
@customer_only
def order_detail(number):
    order = _own_order(number)
    reviewed = {r.product_id for r in ProductReview.query.filter_by(user_id=current_user.id)}
    return render_template("account/order_detail.html", order=order, flow=OrderStatus.FLOW,
                           cancel_form=CancelOrderForm(), reviewed=reviewed)


@bp.post("/orders/<number>/cancel")
@customer_only
def cancel_order(number):
    order = _own_order(number)
    form = CancelOrderForm()
    if not form.validate_on_submit():
        abort(400)
    if not order.customer_can_cancel:
        flash("This order can no longer be cancelled — it's already being prepared or shipped.", "error")
        return redirect(url_for("account.order_detail", number=number))
    change_status(order, OrderStatus.CANCELLED, form.reason.data or "Cancelled by customer")
    db.session.commit()
    flash(f"Order {order.number} was cancelled. Any demo payment was refunded.", "success")
    return redirect(url_for("account.order_detail", number=number))


@bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    form = ProfileForm(obj=current_user)
    pw_form = PasswordChangeForm(prefix="pw")
    if request.form.get("form") == "profile" and form.validate_on_submit():
        current_user.full_name = form.full_name.data
        current_user.phone = form.phone.data or None
        db.session.commit()
        flash("Profile updated.", "success")
        return redirect(url_for("account.profile"))
    if request.form.get("form") == "password" and pw_form.validate_on_submit():
        if not current_user.check_password(pw_form.current.data):
            pw_form.current.errors.append("Current password is incorrect.")
        else:
            current_user.set_password(pw_form.password.data)
            db.session.commit()
            flash("Password changed.", "success")
            return redirect(url_for("account.profile"))
    return render_template("account/profile.html", form=form, pw_form=pw_form)


@bp.route("/addresses", methods=["GET", "POST"])
@customer_only
def addresses():
    form = AddressForm()
    if form.validate_on_submit():
        first = Address.query.filter_by(user_id=current_user.id).count() == 0
        if form.is_default.data or first:
            Address.query.filter_by(user_id=current_user.id).update({"is_default": False})
        addr = Address(user_id=current_user.id)
        form.populate_obj(addr)
        addr.is_default = bool(form.is_default.data or first)
        db.session.add(addr)
        db.session.commit()
        flash("Address added.", "success")
        return redirect(url_for("account.addresses"))
    items = Address.query.filter_by(user_id=current_user.id).order_by(Address.is_default.desc(), Address.id).all()
    return render_template("account/addresses.html", form=form, addresses=items)


def _own_address(address_id):
    addr = db.session.get(Address, address_id)
    if addr is None or addr.user_id != current_user.id:
        abort(404)
    return addr


@bp.route("/addresses/<int:address_id>/edit", methods=["GET", "POST"])
@customer_only
def edit_address(address_id):
    addr = _own_address(address_id)
    form = AddressForm(obj=addr)
    if form.validate_on_submit():
        if form.is_default.data:
            Address.query.filter_by(user_id=current_user.id).update({"is_default": False})
        form.populate_obj(addr)
        db.session.commit()
        flash("Address updated.", "success")
        return redirect(url_for("account.addresses"))
    return render_template("account/address_edit.html", form=form, address=addr)


@bp.post("/addresses/<int:address_id>/delete")
@customer_only
def delete_address(address_id):
    addr = _own_address(address_id)
    was_default = addr.is_default
    db.session.delete(addr)
    db.session.flush()
    if was_default:
        nxt = Address.query.filter_by(user_id=current_user.id).first()
        if nxt:
            nxt.is_default = True
    db.session.commit()
    flash("Address removed.", "info")
    return redirect(url_for("account.addresses"))


@bp.post("/addresses/<int:address_id>/default")
@customer_only
def default_address(address_id):
    addr = _own_address(address_id)
    Address.query.filter_by(user_id=current_user.id).update({"is_default": False})
    addr.is_default = True
    db.session.commit()
    flash("Default address updated.", "success")
    return redirect(url_for("account.addresses"))


@bp.route("/wishlist")
@customer_only
def wishlist():
    items = WishlistItem.query.filter_by(user_id=current_user.id).order_by(WishlistItem.created_at.desc()).all()
    return render_template("account/wishlist.html", items=[i for i in items if i.product.status == PRODUCT_ACTIVE])


@bp.post("/wishlist/<int:product_id>")
def toggle_wishlist(product_id):
    is_fetch = request.headers.get("X-Requested-With") == "fetch"
    if not current_user.is_authenticated:
        if is_fetch:
            return jsonify(ok=False, login=url_for("auth.login", next=request.referrer or "/"),
                           error="Sign in to save items to your wishlist."), 401
        return redirect(url_for("auth.login", next=request.referrer))
    if current_user.role != "customer":
        if is_fetch:
            return jsonify(ok=False, error="Wishlists are for customer accounts."), 403
        abort(403)
    product = db.session.get(Product, product_id)
    if product is None or product.status != PRODUCT_ACTIVE:
        abort(404)
    item = WishlistItem.query.filter_by(user_id=current_user.id, product_id=product_id).first()
    if item:
        db.session.delete(item)
        saved, msg = False, "Removed from wishlist"
    else:
        db.session.add(WishlistItem(user_id=current_user.id, product_id=product_id))
        saved, msg = True, "Saved to wishlist"
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        saved = True
    if is_fetch:
        return jsonify(ok=True, saved=saved, message=msg)
    flash(msg + ".", "success")
    return redirect(request.referrer or url_for("account.wishlist"))


@bp.route("/notifications")
@customer_only
def notifications():
    notes = Notification.query.filter_by(user_id=current_user.id).order_by(Notification.created_at.desc()).limit(100).all()
    return render_template("account/notifications.html", notes=notes)


@bp.post("/notifications/read")
@customer_only
def read_notifications():
    Notification.query.filter_by(user_id=current_user.id, is_read=False).update({"is_read": True})
    db.session.commit()
    flash("All notifications marked as read.", "success")
    return redirect(url_for("account.notifications"))


@bp.route("/notifications/<int:note_id>")
@customer_only
def open_notification(note_id):
    note = db.session.get(Notification, note_id)
    if note is None or note.user_id != current_user.id:
        abort(404)
    note.is_read = True
    db.session.commit()
    link = note.link if note.link and note.link.startswith("/") and not note.link.startswith("//") else url_for("account.notifications")
    return redirect(link)
