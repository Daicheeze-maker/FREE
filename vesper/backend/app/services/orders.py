import secrets
import uuid

from fastapi import HTTPException
from sqlalchemy import delete, update
from sqlalchemy.orm import Session

from ..config import MAX_QTY_PER_LINE, SHIPPING_FEE_CENTAVOS, env
from ..models import Cart, CartItem, Customer, Order, OrderItem, Payment, Product, now
from ..schemas import CheckoutIn
from . import paymongo


# ---- cart -----------------------------------------------------------------

def get_cart(db: Session, cart_id: str) -> Cart:
    cart = db.get(Cart, cart_id)
    if not cart:
        raise HTTPException(404, "Cart not found.")
    return cart


def new_cart(db: Session) -> Cart:
    cart = Cart(id=str(uuid.uuid4()))
    db.add(cart)
    db.commit()
    return cart


def _check_stock(product: Product, quantity: int):
    if product.stock <= 0:
        raise HTTPException(409, f"{product.name} is out of stock.")
    if quantity > product.stock:
        raise HTTPException(409, f"Only {product.stock} of {product.name} left in stock.")
    if quantity > MAX_QTY_PER_LINE:
        raise HTTPException(422, f"Maximum {MAX_QTY_PER_LINE} per item.")


def add_item(db: Session, cart_id: str, product_id: str, quantity: int) -> Cart:
    cart = get_cart(db, cart_id)
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(404, "Product not found.")
    item = next((i for i in cart.items if i.product_id == product_id), None)
    total = quantity + (item.quantity if item else 0)
    _check_stock(product, total)
    if item:
        item.quantity = total
    else:
        cart.items.append(CartItem(product_id=product_id, quantity=quantity))
    db.commit()
    return cart


def set_quantity(db: Session, cart_id: str, product_id: str, quantity: int) -> Cart:
    cart = get_cart(db, cart_id)
    item = next((i for i in cart.items if i.product_id == product_id), None)
    if not item:
        raise HTTPException(404, "Item is not in the cart.")
    _check_stock(item.product, quantity)
    item.quantity = quantity
    db.commit()
    return cart


def remove_item(db: Session, cart_id: str, product_id: str) -> Cart:
    cart = get_cart(db, cart_id)
    item = next((i for i in cart.items if i.product_id == product_id), None)
    if not item:
        raise HTTPException(404, "Item is not in the cart.")
    cart.items.remove(item)
    db.commit()
    return cart


def cart_totals(cart: Cart) -> dict:
    subtotal = sum(i.product.price_centavos * i.quantity for i in cart.items)
    shipping = SHIPPING_FEE_CENTAVOS if cart.items else 0
    return {
        "item_count": sum(i.quantity for i in cart.items),
        "subtotal_centavos": subtotal,
        "shipping_centavos": shipping,
        "total_centavos": subtotal + shipping,
    }


# ---- checkout -------------------------------------------------------------

def payment_mode() -> str:
    return env("PAYMENT_MODE", "mock").lower()


def checkout(db: Session, data: CheckoutIn) -> Order:
    cart = get_cart(db, data.cart_id)
    if not cart.items:
        raise HTTPException(422, "Your cart is empty.")
    for item in cart.items:  # re-validate against current stock, prices come from the DB
        _check_stock(item.product, item.quantity)
    mode = payment_mode()
    if mode not in ("mock", "paymongo"):
        raise HTTPException(500, "PAYMENT_MODE must be 'mock' or 'paymongo'.")

    totals = cart_totals(cart)
    customer = Customer(**data.customer.model_dump())
    order = Order(
        id="VSP-" + secrets.token_hex(5).upper(),
        customer=customer,
        cart_id=cart.id,
        payment_method=data.payment_method,
        subtotal_centavos=totals["subtotal_centavos"],
        shipping_centavos=totals["shipping_centavos"],
        total_centavos=totals["total_centavos"],
        items=[
            OrderItem(product_id=i.product_id, name=i.product.name, seller_name=i.product.seller.name,
                      unit_price_centavos=i.product.price_centavos, quantity=i.quantity)
            for i in cart.items
        ],
    )
    order.payment = Payment(provider=mode, amount_centavos=order.total_centavos)
    db.add(order)
    db.flush()

    frontend = env("FRONTEND_URL", "http://localhost:5173").rstrip("/")
    if mode == "mock":
        order.payment.checkout_url = f"{frontend}/pay/mock/{order.id}"
    else:
        try:
            session = paymongo.create_checkout_session(
                order, [data.payment_method],
                success_url=f"{frontend}/order/{order.id}?result=success",
                cancel_url=f"{frontend}/order/{order.id}?result=cancelled",
            )
        except paymongo.PayMongoError as exc:
            db.rollback()
            raise HTTPException(exc.status, str(exc))
        order.payment.checkout_session_id = session["id"]
        order.payment.payment_intent_id = session["payment_intent_id"]
        order.payment.checkout_url = session["checkout_url"]
    db.commit()
    return order


def mark_paid(db: Session, order: Order) -> bool:
    """Idempotent: only the first transition to 'paid' deducts stock. Returns True if this call did it."""
    claimed = db.execute(
        update(Order).where(Order.id == order.id, Order.status.in_(("pending", "failed")))
        .values(status="paid", paid_at=now())
    ).rowcount
    if not claimed:
        db.rollback()
        return False
    short = []
    for item in order.items:
        ok = db.execute(
            update(Product).where(Product.id == item.product_id, Product.stock >= item.quantity)
            .values(stock=Product.stock - item.quantity)
        ).rowcount
        if not ok:
            short.append(item.name)
    if short:
        # shortcut: paid orders with a stock shortfall are flagged for manual handling, not auto-refunded;
        # add stock reservation at checkout if this happens often.
        order.note = "Stock shortfall at payment time: " + ", ".join(short)
    order.payment.status = "paid"
    if order.cart_id:
        db.execute(delete(CartItem).where(CartItem.cart_id == order.cart_id))
    db.commit()
    db.refresh(order)
    return True


def mark_failed(db: Session, order: Order) -> bool:
    changed = db.execute(update(Order).where(Order.id == order.id, Order.status == "pending")
                         .values(status="failed")).rowcount
    if changed:
        order.payment.status = "failed"
    db.commit()
    db.refresh(order)
    return bool(changed)
