"""Cart storage: session cart for guests, database cart for signed-in customers."""
from dataclasses import dataclass

from flask import session
from flask_login import current_user

from ..extensions import db
from ..models import PRODUCT_ACTIVE, Cart, CartItem, Product

MAX_QTY_PER_LINE = 20
SESSION_KEY = "cart"


@dataclass
class CartLine:
    product: Product
    quantity: int

    @property
    def line_total_minor(self):
        return self.product.price_minor * self.quantity

    @property
    def problem(self):
        if self.product.status != PRODUCT_ACTIVE:
            return "No longer available"
        if self.product.stock < self.quantity:
            return "Sold out" if self.product.stock == 0 else f"Only {self.product.stock} available"
        return None


def _uses_db():
    return current_user.is_authenticated


def _db_cart(create=False):
    cart = Cart.query.filter_by(user_id=current_user.id).first()
    if cart is None and create:
        cart = Cart(user_id=current_user.id)
        db.session.add(cart)
        db.session.flush()
    return cart


def _session_items():
    raw = session.get(SESSION_KEY) or {}
    clean = {}
    for pid, qty in raw.items():
        try:
            pid, qty = int(pid), int(qty)
        except (TypeError, ValueError):
            continue
        if qty > 0:
            clean[pid] = min(qty, MAX_QTY_PER_LINE)
    return clean


def _save_session(items):
    session[SESSION_KEY] = {str(k): v for k, v in items.items()}
    session.modified = True


def get_quantities():
    if _uses_db():
        cart = _db_cart()
        return {i.product_id: i.quantity for i in cart.items} if cart else {}
    return _session_items()


def get_lines():
    qtys = get_quantities()
    if not qtys:
        return []
    products = {p.id: p for p in Product.query.filter(Product.id.in_(qtys.keys())).all()}
    return [CartLine(products[pid], q) for pid, q in qtys.items() if pid in products]


def count():
    return sum(get_quantities().values())


def subtotal_minor(lines=None):
    lines = get_lines() if lines is None else lines
    return sum(l.line_total_minor for l in lines)


def set_quantity(product, quantity, add=False):
    """Set (or add to) a line's quantity, clamped to stock and per-line max. Returns final qty."""
    if product.status != PRODUCT_ACTIVE:
        raise ValueError("This product is not available.")
    current = get_quantities().get(product.id, 0)
    wanted = current + quantity if add else quantity
    wanted = max(0, min(wanted, MAX_QTY_PER_LINE, product.stock))
    if add and quantity > 0 and wanted <= current:
        raise ValueError("No more stock available for this item." if product.stock <= current
                         else f"You can add up to {MAX_QTY_PER_LINE} of one item.")
    if _uses_db():
        cart = _db_cart(create=True)
        item = CartItem.query.filter_by(cart_id=cart.id, product_id=product.id).first()
        if wanted == 0:
            if item:
                db.session.delete(item)
        elif item:
            item.quantity = wanted
        else:
            db.session.add(CartItem(cart_id=cart.id, product_id=product.id, quantity=wanted))
        db.session.commit()
    else:
        items = _session_items()
        if wanted == 0:
            items.pop(product.id, None)
        else:
            items[product.id] = wanted
        _save_session(items)
    return wanted


def remove(product_id):
    if _uses_db():
        cart = _db_cart()
        if cart:
            CartItem.query.filter_by(cart_id=cart.id, product_id=product_id).delete()
            db.session.commit()
    else:
        items = _session_items()
        items.pop(int(product_id), None)
        _save_session(items)


def clear():
    if _uses_db():
        cart = _db_cart()
        if cart:
            CartItem.query.filter_by(cart_id=cart.id).delete()
    session.pop(SESSION_KEY, None)
    session.pop("discount_code", None)


def merge_session_cart_into(user):
    """Called right after login: fold the guest's session cart into their saved cart."""
    guest = _session_items()
    if not guest:
        return
    cart = Cart.query.filter_by(user_id=user.id).first()
    if cart is None:
        cart = Cart(user_id=user.id)
        db.session.add(cart)
        db.session.flush()
    existing = {i.product_id: i for i in cart.items}
    products = {p.id: p for p in Product.query.filter(Product.id.in_(guest.keys())).all()}
    for pid, qty in guest.items():
        product = products.get(pid)
        if not product or product.status != PRODUCT_ACTIVE or product.stock <= 0:
            continue
        if pid in existing:
            existing[pid].quantity = min(existing[pid].quantity + qty, MAX_QTY_PER_LINE, product.stock)
        else:
            db.session.add(CartItem(cart_id=cart.id, product_id=pid, quantity=min(qty, MAX_QTY_PER_LINE, product.stock)))
    db.session.commit()
    session.pop(SESSION_KEY, None)
