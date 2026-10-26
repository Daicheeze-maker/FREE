import json
import secrets
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .config import SHIPPING_FEE_CENTAVOS, env
from .db import SessionLocal, get_db
from .models import Order, Payment, Product, Seller, Subscriber, WebhookEvent
from .schemas import CartItemIn, CheckoutIn, MockOutcomeIn, NewsletterIn, ProductIn, ProductOut, QuantityIn, SellerIn, SellerOut
from .seed import init_db, seed
from .services import currency, orders, paymongo
from .services.catalog import create_product, create_seller, search_products


@asynccontextmanager
async def lifespan(_):
    if env("AUTO_SEED", "1") == "1":
        init_db()
        with SessionLocal() as db:
            seed(db)
    yield


app = FastAPI(title="Vesper Perfume Marketplace API", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in env("CORS_ORIGINS", "http://localhost:5173").split(",")],
    allow_methods=["*"],
    allow_headers=["*"],
)


def require_admin(x_admin_token: str = Header(default="")):
    token = env("ADMIN_TOKEN")
    if not token or not secrets.compare_digest(x_admin_token, token):
        raise HTTPException(403, "Admin token required.")


# ---- catalog --------------------------------------------------------------

@app.get("/api/health")
def health():
    return {"ok": True, "payment_mode": orders.payment_mode(), "shipping_centavos": SHIPPING_FEE_CENTAVOS}


@app.get("/api/sellers", response_model=list[dict])
def list_sellers(db: Session = Depends(get_db)):
    return [{**SellerOut.model_validate(s).model_dump(), "product_count": len(s.products)}
            for s in db.scalars(select(Seller).order_by(Seller.founded))]


@app.get("/api/sellers/{seller_id}")
def get_seller(seller_id: str, db: Session = Depends(get_db)):
    seller = db.get(Seller, seller_id)
    if not seller:
        raise HTTPException(404, "Seller not found.")
    return {**SellerOut.model_validate(seller).model_dump(), "product_count": len(seller.products),
            "products": [ProductOut.model_validate(p) for p in seller.products]}


@app.get("/api/products", response_model=list[ProductOut])
def list_products(
    q: str | None = Query(None, max_length=80),
    seller: list[str] | None = Query(None),
    family: list[str] | None = Query(None),
    min_price: int | None = Query(None, ge=0),
    max_price: int | None = Query(None, ge=0),
    sort: str | None = Query(None, pattern="^(price_asc|price_desc|name_asc|name_desc)$"),
    db: Session = Depends(get_db),
):
    if min_price is not None and max_price is not None and min_price > max_price:
        raise HTTPException(422, "min_price cannot be greater than max_price.")
    return search_products(db, q, seller, family, min_price, max_price, sort)


@app.get("/api/products/{product_id}")
def get_product(product_id: str, db: Session = Depends(get_db)):
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(404, "Product not found.")
    related = [ProductOut.model_validate(p) for p in product.seller.products if p.id != product.id]
    return {"product": ProductOut.model_validate(product), "related": related}


@app.post("/api/admin/sellers", status_code=201, dependencies=[Depends(require_admin)], response_model=SellerOut)
def admin_create_seller(data: SellerIn, db: Session = Depends(get_db)):
    seller = create_seller(db, data)
    db.commit()
    return seller


@app.post("/api/admin/products", status_code=201, dependencies=[Depends(require_admin)], response_model=ProductOut)
def admin_create_product(data: ProductIn, db: Session = Depends(get_db)):
    product = create_product(db, data)
    db.commit()
    return product


@app.post("/api/newsletter", status_code=201)
def subscribe(data: NewsletterIn, db: Session = Depends(get_db)):
    email = data.email.lower()
    if db.get(Subscriber, email):
        return {"subscribed": True, "already": True}
    db.add(Subscriber(email=email))
    db.commit()
    return {"subscribed": True, "already": False}


# ---- currency -------------------------------------------------------------

@app.get("/api/currency/rate")
def currency_rate(to: str = "USD", base: str = "PHP"):
    try:
        return currency.get_rate(base, to)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    except currency.RateUnavailable:
        raise HTTPException(503, "Exchange rates are unavailable right now. Prices are shown in PHP.")


# ---- cart -----------------------------------------------------------------

def cart_out(cart, currency_code: str = "PHP"):
    out = {
        "id": cart.id,
        "items": [{"product": ProductOut.model_validate(i.product), "quantity": i.quantity,
                   "line_total_centavos": i.product.price_centavos * i.quantity} for i in cart.items],
        **orders.cart_totals(cart),
        "display": None,
    }
    if currency_code != "PHP":
        out["display"] = convert_totals(out, currency_code)
    return out


def convert_totals(totals: dict, code: str):
    # Fallback to PHP (display=None) if rates are down; checkout always charges PHP anyway.
    try:
        rate = currency.get_rate("PHP", code)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    except currency.RateUnavailable:
        return None
    conv = {k.replace("_centavos", ""): str(currency.convert_centavos(totals[k], rate["rate"]))
            for k in ("subtotal_centavos", "shipping_centavos", "total_centavos")}
    return {"currency": code, "rate": rate["rate"], "date": rate["date"], **conv}


@app.post("/api/carts", status_code=201)
def create_cart(db: Session = Depends(get_db)):
    return cart_out(orders.new_cart(db))


@app.get("/api/carts/{cart_id}")
def read_cart(cart_id: str, currency_code: str = Query("PHP", alias="currency"), db: Session = Depends(get_db)):
    return cart_out(orders.get_cart(db, cart_id), currency_code.upper())


@app.post("/api/carts/{cart_id}/items")
def add_to_cart(cart_id: str, data: CartItemIn, db: Session = Depends(get_db)):
    return cart_out(orders.add_item(db, cart_id, data.product_id, data.quantity))


@app.patch("/api/carts/{cart_id}/items/{product_id}")
def update_cart_item(cart_id: str, product_id: str, data: QuantityIn, db: Session = Depends(get_db)):
    return cart_out(orders.set_quantity(db, cart_id, product_id, data.quantity))


@app.delete("/api/carts/{cart_id}/items/{product_id}")
def delete_cart_item(cart_id: str, product_id: str, db: Session = Depends(get_db)):
    return cart_out(orders.remove_item(db, cart_id, product_id))


# ---- orders & payments ----------------------------------------------------

def order_out(order: Order):
    return {
        "id": order.id,
        "status": order.status,
        "payment_method": order.payment_method,
        "payment_provider": order.payment.provider,
        "payment_status": order.payment.status,
        "subtotal_centavos": order.subtotal_centavos,
        "shipping_centavos": order.shipping_centavos,
        "total_centavos": order.total_centavos,
        "created_at": order.created_at,
        "paid_at": order.paid_at,
        "customer": {"name": order.customer.name, "email": order.customer.email},
        "items": [{"product_id": i.product_id, "name": i.name, "seller_name": i.seller_name,
                   "unit_price_centavos": i.unit_price_centavos, "quantity": i.quantity} for i in order.items],
    }


def load_order(db: Session, order_id: str) -> Order:
    order = db.get(Order, order_id)
    if not order:
        raise HTTPException(404, "Order not found.")
    return order


@app.post("/api/checkout", status_code=201)
def create_checkout(data: CheckoutIn, db: Session = Depends(get_db)):
    order = orders.checkout(db, data)
    return {"order": order_out(order), "checkout_url": order.payment.checkout_url}


@app.get("/api/orders/{order_id}")
def read_order(order_id: str, db: Session = Depends(get_db)):
    return order_out(load_order(db, order_id))


@app.post("/api/orders/{order_id}/verify")
def verify_order(order_id: str, db: Session = Depends(get_db)):
    """Called after the PayMongo redirect. The redirect itself proves nothing; we ask PayMongo."""
    order = load_order(db, order_id)
    if order.status == "pending" and order.payment.provider == "paymongo" and order.payment.checkout_session_id:
        try:
            status = paymongo.session_payment_status(order.payment.checkout_session_id)
        except paymongo.PayMongoError as exc:
            raise HTTPException(exc.status, str(exc))
        if status == "paid":
            orders.mark_paid(db, order)
        elif status == "failed":
            orders.mark_failed(db, order)
    return order_out(order)


@app.post("/api/payments/mock/{order_id}")
def mock_payment(order_id: str, data: MockOutcomeIn, db: Session = Depends(get_db)):
    """Local demo gateway. Disabled when PAYMENT_MODE=paymongo."""
    if orders.payment_mode() != "mock":
        raise HTTPException(403, "Mock payments are disabled.")
    order = load_order(db, order_id)
    if order.payment.provider != "mock":
        raise HTTPException(409, "This order was not created in mock mode.")
    (orders.mark_paid if data.outcome == "paid" else orders.mark_failed)(db, order)
    return order_out(order)


@app.post("/api/webhooks/paymongo")
async def paymongo_webhook(request: Request, db: Session = Depends(get_db)):
    secret = env("PAYMONGO_WEBHOOK_SECRET")
    if not secret:
        raise HTTPException(503, "Webhook secret not configured.")
    raw = await request.body()
    if not paymongo.verify_signature(raw, request.headers.get("paymongo-signature", ""), secret):
        raise HTTPException(400, "Invalid signature.")
    try:
        event = json.loads(raw)["data"]
        event_id, attrs = event["id"], event["attributes"]
        etype, resource = attrs["type"], attrs["data"]
    except (ValueError, KeyError, TypeError):
        raise HTTPException(400, "Malformed event.")
    if attrs.get("livemode"):
        raise HTTPException(400, "Live events are not accepted by this prototype.")

    db.add(WebhookEvent(id=event_id, type=etype))
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        return {"received": True, "duplicate": True}

    payment = None
    if etype == "checkout_session.payment.paid":
        payment = db.scalar(select(Payment).where(Payment.checkout_session_id == resource.get("id")))
    elif etype == "payment.failed":
        pi = (resource.get("attributes") or {}).get("payment_intent_id")
        payment = db.scalar(select(Payment).where(Payment.payment_intent_id == pi)) if pi else None
    db.commit()  # record the event even if it is not one we act on

    if payment:
        if etype == "checkout_session.payment.paid":
            orders.mark_paid(db, payment.order)
        else:
            orders.mark_failed(db, payment.order)
    return {"received": True, "duplicate": False, "matched": payment is not None}
