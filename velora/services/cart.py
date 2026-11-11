"""Cart storage: session cart for guests, database cart for signed-in customers.

A cart line is identified by (product, size): the same jacket in M and in L are two lines.
Stock is tracked per product, so all sizes of a product share its stock.
"""
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
    size: str = ""

    @property
    def line_total_minor(self):
        return self.product.price_minor * self.quantity

    @property
    def problem(self):
        if self.product.status != PRODUCT_ACTIVE:
            return "No longer available"
        if self.product.size_list and self.size not in self.product.size_list:
            return "Choose a size"
        if self.product.stock < self.quantity:
            return "Sold out" if self.product.stock == 0 else f"Only {self.product.stock} available"
        return None


def clean_size(product, size):
    """Validate the size a shopper picked. Products without sizes always use ''."""
    size = (size or "").strip()
    options = product.size_list
    if not options:
        return ""
    if size not in options:
        raise ValueError("Please choose a size." if not size else f"“{size[:20]}” isn't available for this item.")
    return size


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
    for key, qty in raw.items():
        pid, _, size = str(key).partition(":")
        try:
            pid, qty = int(pid), int(qty)
        except (TypeError, ValueError):
            continue
        if qty > 0:
            clean[(pid, size)] = min(qty, MAX_QTY_PER_LINE)
    return clean


def _save_session(items):
    session[SESSION_KEY] = {f"{pid}:{size}": qty for (pid, size), qty in items.items()}
    session.modified = True


def get_quantities():
    """{(product_id, size): quantity}"""
    if _uses_db():
        cart = _db_cart()
        return {(i.product_id, i.size or ""): i.quantity for i in cart.items} if cart else {}
    return _session_items()


def get_lines():
    qtys = get_quantities()
    if not qtys:
        return []
    products = {p.id: p for p in Product.query.filter(Product.id.in_({pid for pid, _ in qtys})).all()}
    return [CartLine(products[pid], q, size) for (pid, size), q in qtys.items() if pid in products]


def count():
    return sum(get_quantities().values())


def subtotal_minor(lines=None):
    lines = get_lines() if lines is None else lines
    return sum(l.line_total_minor for l in lines)


def set_quantity(product, quantity, size="", add=False):
    """Set (or add to) a line's quantity, clamped to stock and the per-line max. Returns the final quantity."""
    if product.status != PRODUCT_ACTIVE:
        raise ValueError("This product is not available.")
    size = clean_size(product, size)
    quantities = get_quantities()
    current = quantities.get((product.id, size), 0)
    in_other_sizes = sum(q for (pid, s), q in quantities.items() if pid == product.id and s != size)
    room = max(0, product.stock - in_other_sizes)  # stock is shared by all sizes of the product
    wanted = current + quantity if add else quantity
    wanted = max(0, min(wanted, MAX_QTY_PER_LINE, room))
    if add and quantity > 0 and wanted <= current:
        raise ValueError("No more stock available for this item." if room <= current
                         else f"You can add up to {MAX_QTY_PER_LINE} of one item.")
    if _uses_db():
        cart = _db_cart(create=True)
        item = CartItem.query.filter_by(cart_id=cart.id, product_id=product.id, size=size).first()
        if wanted == 0:
            if item:
                db.session.delete(item)
        elif item:
            item.quantity = wanted
        else:
            db.session.add(CartItem(cart_id=cart.id, product_id=product.id, size=size, quantity=wanted))
        db.session.commit()
    else:
        items = _session_items()
        if wanted == 0:
            items.pop((product.id, size), None)
        else:
            items[(product.id, size)] = wanted
        _save_session(items)
    return wanted


def remove(product_id, size=""):
    size = (size or "").strip()
    if _uses_db():
        cart = _db_cart()
        if cart:
            CartItem.query.filter_by(cart_id=cart.id, product_id=product_id, size=size).delete()
            db.session.commit()
    else:
        items = _session_items()
        items.pop((int(product_id), size), None)
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
    existing = {(i.product_id, i.size or ""): i for i in cart.items}
    products = {p.id: p for p in Product.query.filter(Product.id.in_({pid for pid, _ in guest})).all()}
    for (pid, size), qty in guest.items():
        product = products.get(pid)
        if not product or product.status != PRODUCT_ACTIVE or product.stock <= 0:
            continue
        if product.size_list and size not in product.size_list:
            continue  # a size that no longer exists can't be bought
        if (pid, size) in existing:
            existing[(pid, size)].quantity = min(existing[(pid, size)].quantity + qty, MAX_QTY_PER_LINE, product.stock)
        else:
            db.session.add(CartItem(cart_id=cart.id, product_id=pid, size=size,
                                    quantity=min(qty, MAX_QTY_PER_LINE, product.stock)))
    db.session.commit()
    session.pop(SESSION_KEY, None)
