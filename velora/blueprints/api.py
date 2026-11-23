"""Aurelune REST API (JSON), version 1: /api/v1/...

* Auth: POST /api/v1/auth/token with {"email", "password"} returns a Bearer token (valid API_TOKEN_HOURS hours).
  Send it as `Authorization: Bearer <token>`. The API never uses the website's login cookie, so it needs no CSRF token.
* Success: the resource as JSON (lists: {"items": [...], "page", "per_page", "total", "pages"}).
* Errors: {"error": {"status": 404, "code": "not_found", "message": "...", "fields": {...}}} with a matching HTTP status.
* Money is in PHP. Every amount comes as *_minor (centavos, an integer) and as a formatted string.

The endpoint list below (ENDPOINTS) feeds GET /api/v1 and the /api/docs page; a test checks that it matches the routes.
"""
import secrets
import time
from datetime import timedelta

import requests
from flask import Blueprint, current_app, g, jsonify, render_template, request, url_for
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from sqlalchemy import text

from .. import phones
from ..extensions import csrf, db
from ..models import (PRODUCT_ACTIVE, PRODUCT_ARCHIVED, PRODUCT_STATUSES, ROLE_CUSTOMER, Address, Cart, CartItem,
                      Category, Order, OrderStatus, Product, ProductImage, User, utcnow)
from ..money import fmt_minor
from ..security import audit
from ..services import cart as cart_service, currency, mapbox, nominatim
from ..services.catalog import SORTS, next_sku, search_products, unique_slug, visible_products
from ..services.orders import CheckoutError, ShipTo, change_status, place_order
from ..services.payments import DEMO_CREDIT

bp = Blueprint("api", __name__, url_prefix="/api/v1")
csrf.exempt(bp)  # Bearer-token API: the session cookie is ignored below, so cross-site form posts can't act as anyone

STAFF = ("seller", "admin")

# method, path, who may call it, what it does
ENDPOINTS = [
    ("GET", "/api/v1", "anyone", "This list of endpoints."),
    ("GET", "/api/v1/health", "anyone", "Server, database and outside-API status."),
    ("POST", "/api/v1/auth/token", "anyone", "Sign in with email and password; returns a Bearer token."),
    ("GET", "/api/v1/me", "signed in", "The signed-in account (role, demo credit)."),
    ("GET", "/api/v1/categories", "anyone", "The watch collections with product counts."),
    ("GET", "/api/v1/products", "anyone", "Search and list watches (q, category, brand, min_price, max_price, in_stock, sort, page, per_page)."),
    ("GET", "/api/v1/products/<id or slug>", "anyone", "One watch with its options, stock and photos."),
    ("POST", "/api/v1/products", "seller, admin", "Create a watch."),
    ("PATCH", "/api/v1/products/<id>", "seller, admin", "Change some fields of a watch."),
    ("DELETE", "/api/v1/products/<id>", "seller, admin", "Archive a watch (kept for order history)."),
    ("GET", "/api/v1/cart", "buyer", "The bag with prices, totals and any stock problems."),
    ("POST", "/api/v1/cart/items", "buyer", "Add a watch (product_id, quantity, size, color, engraving)."),
    ("PATCH", "/api/v1/cart/items/<id>", "buyer", "Change a bag line's quantity (0 removes it)."),
    ("DELETE", "/api/v1/cart/items/<id>", "buyer", "Remove one bag line."),
    ("DELETE", "/api/v1/cart", "buyer", "Empty the bag."),
    ("GET", "/api/v1/orders", "signed in", "Your orders (staff: every order; filter with status)."),
    ("POST", "/api/v1/orders", "buyer", "Place an order from the bag, paid with demo credit (Idempotency-Key header supported)."),
    ("GET", "/api/v1/orders/<number>", "owner, seller, admin", "One order with its items and delivery address."),
    ("PATCH", "/api/v1/orders/<number>", "seller, admin", "Move an order to its next status (e.g. delivered)."),
    ("POST", "/api/v1/orders/<number>/cancel", "owner", "Cancel your order while it can still be cancelled."),
    ("GET", "/api/v1/rates", "anyone", "Display-currency exchange rates (outside API: Frankfurter / ECB)."),
    ("GET", "/api/v1/geocode/reverse", "signed in", "Map pin to street address (outside API: Mapbox, else OpenStreetMap Nominatim)."),
]


# ------------------------------------------------------------------ errors

class ApiError(Exception):
    def __init__(self, status, code, message, fields=None, headers=None):
        super().__init__(message)
        self.status, self.code, self.message, self.fields, self.headers = status, code, message, fields, headers or {}


def error_response(status, code, message, fields=None, headers=None):
    body = {"status": status, "code": code, "message": message}
    if fields:
        body["fields"] = fields
    resp = jsonify(error=body)
    resp.status_code = status
    for k, v in (headers or {}).items():
        resp.headers[k] = v
    return resp


@bp.errorhandler(ApiError)
def _api_error(exc):
    return error_response(exc.status, exc.code, exc.message, exc.fields, exc.headers)


# ------------------------------------------------------------------ auth (Bearer tokens)

def _serializer():
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt="aurelune-api-token")


def make_token(user):
    # The password-hash tail ties the token to the current password: changing it signs every token out.
    return _serializer().dumps({"uid": user.id, "pw": user.password_hash[-16:]})


def _user_from_token():
    header = request.headers.get("Authorization", "")
    if not header.lower().startswith("bearer "):
        return None
    raw = header[7:].strip()
    try:
        data = _serializer().loads(raw, max_age=int(current_app.config.get("API_TOKEN_HOURS", 24)) * 3600)
    except SignatureExpired:
        raise ApiError(401, "token_expired", "Your token has expired. Get a new one from POST /api/v1/auth/token.",
                       headers={"WWW-Authenticate": 'Bearer error="invalid_token"'})
    except BadSignature:
        raise ApiError(401, "invalid_token", "That token isn't valid.", headers={"WWW-Authenticate": 'Bearer error="invalid_token"'})
    user = db.session.get(User, data.get("uid"))
    if user is None or user.password_hash[-16:] != data.get("pw") or not user.is_active_account:
        raise ApiError(401, "invalid_token", "That token isn't valid any more.", headers={"WWW-Authenticate": 'Bearer error="invalid_token"'})
    return user


@bp.before_request
def _authenticate():
    from flask_login import AnonymousUserMixin
    # Only the Bearer token counts here. Setting g._login_user means Flask-Login never reads the website's cookie.
    try:
        g._login_user = _user_from_token() or AnonymousUserMixin()
    except ApiError:
        g._login_user = AnonymousUserMixin()
        raise
    if request.method in ("POST", "PUT", "PATCH") and request.content_length and not request.is_json:
        raise ApiError(415, "unsupported_media_type", "Send the request body as JSON (Content-Type: application/json).")


def _user(roles=None):
    user = g._login_user
    if not getattr(user, "is_authenticated", False):
        raise ApiError(401, "unauthorized", "Sign in first: POST /api/v1/auth/token, then send Authorization: Bearer <token>.",
                       headers={"WWW-Authenticate": "Bearer"})
    if roles and user.role not in roles:
        raise ApiError(403, "forbidden", "Your account can't do this.")
    return user


def _body():
    data = request.get_json(silent=True)
    if data is None:
        if request.content_length:
            raise ApiError(400, "bad_json", "The request body isn't valid JSON.")
        data = {}
    if not isinstance(data, dict):
        raise ApiError(400, "bad_json", "The request body must be a JSON object.")
    return data


# ------------------------------------------------------------------ shapes

def _money(minor):
    return {"minor": int(minor or 0), "formatted": fmt_minor(minor or 0)}


def _image_url(img):
    if img is None:
        return None
    if img.filename:
        return url_for("main.media", filename=img.filename)
    return img.url


def product_json(p, full=False):
    data = {
        "id": p.id, "slug": p.slug, "sku": p.sku, "name": p.name, "brand": p.brand,
        "category": p.category.slug if p.category else None, "status": p.status,
        "price": _money(p.price_minor), "compare_at": _money(p.compare_at_minor) if p.compare_at_minor else None,
        "stock": p.stock, "in_stock": p.stock > 0, "image": _image_url(p.primary_image),
        "url": url_for("catalog.detail", slug=p.slug),
    }
    if full:
        data.update({
            "short_description": p.short_description, "description": p.description, "specs": p.ingredients,
            "origin": p.origin, "sizes": p.size_list, "colors": p.color_list,
            "engraving": {"fee": _money(p.engraving_fee_minor), "max_chars": p.engraving_max or 20} if p.offers_engraving else None,
            "is_featured": p.is_featured, "sold": p.sold_count,
            "images": [_image_url(i) for i in p.images],
        })
    return data


def order_json(o, full=False):
    data = {"number": o.number, "status": o.status, "placed_at": o.created_at.isoformat() + "Z" if o.created_at else None,
            "item_count": o.item_count, "total": _money(o.total_minor), "currency": o.currency,
            "url": url_for("account.order_detail", number=o.number)}
    if full:
        data.update({
            "subtotal": _money(o.subtotal_minor), "discount": _money(o.discount_minor), "shipping": _money(o.shipping_minor),
            "discount_code": o.discount_code, "notes": o.notes,
            "ship_to": {"name": o.ship_name, "phone": o.ship_phone, "address": o.ship_address},
            "items": [{"product_id": i.product_id, "name": i.product_name, "sku": i.product_sku, "options": i.size,
                       "quantity": i.quantity, "unit_price": _money(i.unit_price_minor), "line_total": _money(i.line_total_minor)}
                      for i in o.items],
            "payment": ({"method": o.payment.method, "status": o.payment.status, "reference": o.payment.reference}
                        if o.payment else None),
            "can_cancel": o.customer_can_cancel,
        })
    return data


def _page(query, shape):
    try:
        page = max(1, int(request.args.get("page", 1)))
        per_page = min(50, max(1, int(request.args.get("per_page", 20))))
    except ValueError:
        raise ApiError(400, "bad_request", "page and per_page must be whole numbers.")
    result = query.paginate(page=page, per_page=per_page, error_out=False)
    return jsonify(items=[shape(x) for x in result.items], page=page, per_page=per_page, total=result.total,
                   pages=result.pages)


# ------------------------------------------------------------------ index, health, auth

@bp.get("")
def index():
    return jsonify(name=f"{current_app.config['BRAND_NAME']} API", version="v1",
                   docs=url_for("api_docs"), auth="Authorization: Bearer <token from POST /api/v1/auth/token>",
                   endpoints=[{"method": m, "path": p, "who": w, "description": d} for m, p, w, d in ENDPOINTS])


@bp.get("/health")
def health():
    started = time.monotonic()
    try:
        db.session.execute(text("SELECT 1"))
        products = db.session.scalar(text("SELECT COUNT(*) FROM product"))
        database = {"ok": True, "products": products}
    except Exception as exc:  # report, never crash the health check
        db.session.rollback()
        database = {"ok": False, "error": type(exc).__name__}
    from ..models import ApiStatus
    iso = lambda d: d.isoformat() + "Z" if d else None
    apis = {r.name: {"last_ok_at": iso(r.last_success_at), "last_error_at": iso(r.last_error_at),
                     "last_latency_ms": r.last_latency_ms} for r in ApiStatus.query.order_by(ApiStatus.name)}
    body = {"status": "ok" if database["ok"] else "error", "database": database, "outside_apis": apis,
            "time": utcnow().isoformat() + "Z", "took_ms": int((time.monotonic() - started) * 1000)}
    return jsonify(body), (200 if database["ok"] else 503)


@bp.post("/auth/token")
def token():
    from .auth import _ip_throttled
    data = _body()
    email = str(data.get("email") or "").strip().lower()
    password = str(data.get("password") or "")
    fields = {k: "Required." for k, v in (("email", email), ("password", password)) if not v}
    if fields:
        raise ApiError(422, "validation_failed", "Email and password are required.", fields)
    if _ip_throttled():
        raise ApiError(429, "too_many_attempts", "Too many sign-in attempts. Wait a few minutes.", headers={"Retry-After": "300"})
    user = User.query.filter_by(email=email).first()
    now = utcnow()
    if user and user.locked_until and user.locked_until > now:
        raise ApiError(429, "locked", "Too many failed attempts on this account. Try again later.",
                       headers={"Retry-After": str(int((user.locked_until - now).total_seconds()) + 1)})
    if not user or not user.check_password(password):
        if user:
            user.failed_login_count += 1
            if user.failed_login_count >= current_app.config["LOGIN_MAX_ATTEMPTS"]:
                user.locked_until = now + timedelta(minutes=current_app.config["LOGIN_LOCK_MINUTES"])
                user.failed_login_count = 0
            db.session.commit()
        raise ApiError(401, "invalid_credentials", "That email and password don't match.")
    if not user.is_active_account:
        raise ApiError(403, "account_disabled", "This account has been disabled.")
    user.failed_login_count, user.locked_until, user.last_login_at = 0, None, now
    db.session.commit()
    hours = int(current_app.config.get("API_TOKEN_HOURS", 24))
    return jsonify(token=make_token(user), token_type="Bearer", expires_in=hours * 3600, user=_me_json(user))


def _me_json(u):
    return {"id": u.id, "email": u.email, "name": u.full_name, "role": u.role,
            "demo_credit": _money(u.balance_minor) if u.role == ROLE_CUSTOMER else None}


@bp.get("/me")
def me():
    return jsonify(_me_json(_user()))


# ------------------------------------------------------------------ catalog

@bp.get("/categories")
def categories():
    counts = dict(db.session.query(Product.category_id, db.func.count(Product.id))
                  .filter(Product.status == PRODUCT_ACTIVE).group_by(Product.category_id).all())
    return jsonify(items=[{"id": c.id, "slug": c.slug, "name": c.name, "description": c.description,
                           "product_count": counts.get(c.id, 0)}
                          for c in Category.query.order_by(Category.position, Category.name)])


def _peso_arg(name):
    raw = request.args.get(name)
    if raw in (None, ""):
        return None
    try:
        value = float(raw)
    except ValueError:
        raise ApiError(400, "bad_request", f"{name} must be a number of pesos.")
    if value < 0:
        raise ApiError(400, "bad_request", f"{name} can't be negative.")
    return int(round(value * 100))


@bp.get("/products")
def products():
    category = None
    if request.args.get("category"):
        category = Category.query.filter_by(slug=request.args["category"]).first()
        if category is None:
            raise ApiError(404, "not_found", "No collection with that slug. See GET /api/v1/categories.")
    sort = request.args.get("sort", "featured")
    if sort not in SORTS:
        raise ApiError(400, "bad_request", f"sort must be one of: {', '.join(SORTS)}.")
    brands = [b for b in request.args.getlist("brand") if b] or None
    query = search_products(q=request.args.get("q"), category=category, brands=brands,
                            min_price=_peso_arg("min_price"), max_price=_peso_arg("max_price"),
                            availability="in_stock" if request.args.get("in_stock") in ("1", "true") else None, sort=sort)
    return _page(query, product_json)


def _find_product(ref, staff=False):
    q = Product.query if staff else visible_products()
    product = q.filter(Product.id == int(ref)).first() if str(ref).isdigit() else q.filter(Product.slug == ref).first()
    if product is None:
        raise ApiError(404, "not_found", "No watch with that id or slug.")
    return product


@bp.get("/products/<ref>")
def product_detail(ref):
    user = g._login_user
    staff = getattr(user, "is_authenticated", False) and user.role in STAFF
    return jsonify(product_json(_find_product(ref, staff), full=True))


def _list_field(value, name, max_items, max_len):
    if value is None:
        return None
    parts = value if isinstance(value, list) else str(value).split(",")
    parts = [str(p).strip() for p in parts if str(p).strip()]
    if len(set(parts)) != len(parts) or len(parts) > max_items or any(len(p) > max_len for p in parts):
        raise ValueError(f"Up to {max_items} different values, each under {max_len} characters.")
    return ",".join(parts) or None


def _apply_product_fields(product, data, creating):
    """Validate and copy JSON fields onto a product. Collects every problem before failing (422)."""
    errors = {}

    def text_field(key, attr, min_len, max_len, required):
        if key not in data:
            if creating and required:
                errors[key] = "Required."
            return
        value = str(data[key] or "").strip()
        if required and len(value) < min_len:
            errors[key] = "Required." if not value else f"At least {min_len} characters."
        elif len(value) > max_len:
            errors[key] = f"At most {max_len} characters."
        else:
            setattr(product, attr, value or None if not required else value)

    text_field("name", "name", 2, 200, True)
    text_field("brand", "brand", 1, 120, True)
    text_field("short_description", "short_description", 1, 300, True)
    text_field("description", "description", 1, 8000, True)
    text_field("specs", "ingredients", 0, 4000, False)
    text_field("origin", "origin", 0, 120, False)

    def peso_field(key, attr, required, allow_null):
        if key not in data:
            if creating and required:
                errors[key] = "Required."
            return
        value = data[key]
        if value is None and allow_null:
            setattr(product, attr, None)
            return
        try:
            minor = int(round(float(value) * 100))
        except (TypeError, ValueError):
            errors[key] = "Must be a number of pesos, e.g. 15900."
            return
        if minor <= 0 or minor > 100_000_000_00:
            errors[key] = "Must be more than 0."
            return
        setattr(product, attr, minor)

    peso_field("price", "price_minor", True, False)
    peso_field("compare_at", "compare_at_minor", False, True)
    peso_field("engraving_fee", "engraving_fee_minor", False, True)

    if "stock" in data or creating:
        try:
            stock = int(data.get("stock"))
            if stock < 0 or stock > 100000 or isinstance(data.get("stock"), bool):
                raise ValueError
            product.stock = stock
        except (TypeError, ValueError):
            errors["stock"] = "A whole number from 0 to 100000."
    if "category" in data or creating:
        cat = Category.query.filter_by(slug=str(data.get("category") or "")).first()
        if cat is None:
            errors["category"] = "Use a collection slug from GET /api/v1/categories."
        else:
            product.category = cat
    for key, max_items, max_len in (("sizes", 12, 12), ("colors", 10, 24)):
        if key in data:
            try:
                setattr(product, key, _list_field(data[key], key, max_items, max_len))
            except ValueError as exc:
                errors[key] = str(exc)
    if "engraving_max" in data:
        try:
            n = int(data["engraving_max"])
            if not 1 <= n <= 40:
                raise ValueError
            product.engraving_max = n
        except (TypeError, ValueError):
            errors["engraving_max"] = "A whole number from 1 to 40."
    if "status" in data:
        if data["status"] not in PRODUCT_STATUSES:
            errors["status"] = f"One of: {', '.join(PRODUCT_STATUSES)}."
        else:
            product.status = data["status"]
    if "is_featured" in data:
        product.is_featured = bool(data["is_featured"])
    if "image_url" in data and data["image_url"]:
        url = str(data["image_url"]).strip()
        if not url.startswith("https://") or len(url) > 500:
            errors["image_url"] = "Use an https:// link (up to 500 characters)."
        else:
            for img in product.images:
                img.position += 1
            product.images.insert(0, ProductImage(url=url, alt=product.name or "", position=0))
    if product.compare_at_minor and product.price_minor and product.compare_at_minor <= product.price_minor:
        errors["compare_at"] = "Must be higher than the price (it's the old price shown crossed out)."
    if errors:
        raise ApiError(422, "validation_failed", "Some fields need fixing.", errors)


@bp.post("/products")
def product_create():
    user = _user(STAFF)
    data = _body()
    product = Product(status=PRODUCT_ACTIVE, engraving_max=20, source="manual")
    with db.session.no_autoflush:
        _apply_product_fields(product, data, creating=True)
    product.slug = unique_slug(product.name)
    product.sku = next_sku()
    db.session.add(product)
    db.session.flush()
    audit("product.create", "product", product.id, f"API: created {product.name}", actor=user)
    db.session.commit()
    resp = jsonify(product_json(product, full=True))
    resp.status_code = 201
    resp.headers["Location"] = url_for("api.product_detail", ref=product.id)
    return resp


@bp.patch("/products/<int:product_id>")
def product_update(product_id):
    user = _user(STAFF)
    product = _find_product(product_id, staff=True)
    data = _body()
    if not data:
        raise ApiError(400, "bad_request", "Send at least one field to change.")
    try:
        with db.session.no_autoflush:
            _apply_product_fields(product, data, creating=False)
    except ApiError:
        db.session.rollback()
        raise
    if "name" in data:
        product.slug = unique_slug(product.name, exclude_id=product.id)
    audit("product.update", "product", product.id, f"API: changed {', '.join(sorted(data))[:200]}", actor=user)
    db.session.commit()
    return jsonify(product_json(product, full=True))


@bp.delete("/products/<int:product_id>")
def product_delete(product_id):
    user = _user(STAFF)
    product = _find_product(product_id, staff=True)
    product.status = PRODUCT_ARCHIVED  # archived, not erased: past orders still point at it
    audit("product.archive", "product", product.id, f"API: archived {product.name}", actor=user)
    db.session.commit()
    return "", 204


# ------------------------------------------------------------------ cart

def _cart_json(user):
    cart = Cart.query.filter_by(user_id=user.id).first()
    items, subtotal, count = [], 0, 0
    for item in (cart.items if cart else []):
        line = cart_service.CartLine(item.product, item.quantity, item.size or "")
        size, color, engraving = line.options
        items.append({"id": item.id, "product": product_json(item.product), "quantity": item.quantity,
                      "size": size or None, "color": color or None, "engraving": engraving or None,
                      "unit_price": _money(line.unit_price_minor), "line_total": _money(line.line_total_minor),
                      "problem": line.problem})
        subtotal += line.line_total_minor
        count += item.quantity
    return {"items": items, "count": count, "subtotal": _money(subtotal), "currency": "PHP"}


def _cart_item(user, item_id):
    item = (CartItem.query.join(Cart).filter(CartItem.id == item_id, Cart.user_id == user.id).first())
    if item is None:
        raise ApiError(404, "not_found", "That line isn't in your bag.")
    return item


def _quantity(data, default=None, minimum=1):
    raw = data.get("quantity", default)
    if isinstance(raw, bool):
        raise ApiError(422, "validation_failed", "Check the quantity.", {"quantity": "A whole number."})
    try:
        qty = int(raw)
    except (TypeError, ValueError):
        raise ApiError(422, "validation_failed", "Check the quantity.", {"quantity": "A whole number."})
    if qty < minimum or qty > cart_service.MAX_QTY_PER_LINE:
        raise ApiError(422, "validation_failed", "Check the quantity.",
                       {"quantity": f"From {minimum} to {cart_service.MAX_QTY_PER_LINE}."})
    return qty


@bp.get("/cart")
def cart_view():
    return jsonify(_cart_json(_user((ROLE_CUSTOMER,))))


@bp.post("/cart/items")
def cart_add():
    user = _user((ROLE_CUSTOMER,))
    data = _body()
    try:
        product = _find_product(int(data.get("product_id")))
    except (TypeError, ValueError):
        raise ApiError(422, "validation_failed", "Say which watch to add.", {"product_id": "Required: a product id."})
    qty = _quantity(data, default=1)
    key = cart_service.make_key(str(data.get("size") or ""), str(data.get("color") or ""), str(data.get("engraving") or ""))
    try:
        key = cart_service.clean_size(product, key)
    except ValueError as exc:
        raise ApiError(422, "invalid_options", str(exc))
    if product.stock <= 0:
        raise ApiError(409, "out_of_stock", f"{product.name} is sold out.")
    try:
        cart_service.set_quantity(product, qty, key, add=True)
    except ValueError as exc:
        raise ApiError(409, "not_enough_stock", str(exc))
    resp = jsonify(_cart_json(user))
    resp.status_code = 201
    return resp


@bp.patch("/cart/items/<int:item_id>")
def cart_update(item_id):
    user = _user((ROLE_CUSTOMER,))
    item = _cart_item(user, item_id)
    qty = _quantity(_body(), minimum=0)
    try:
        final = cart_service.set_quantity(item.product, qty, item.size or "")
    except ValueError as exc:
        raise ApiError(409, "not_available", str(exc))
    body = _cart_json(user)
    if final < qty:
        body["warning"] = f"Only {final} could be kept because of stock."
    return jsonify(body)


@bp.delete("/cart/items/<int:item_id>")
def cart_remove(item_id):
    user = _user((ROLE_CUSTOMER,))
    item = _cart_item(user, item_id)
    db.session.delete(item)
    db.session.commit()
    return "", 204


@bp.delete("/cart")
def cart_clear():
    user = _user((ROLE_CUSTOMER,))
    cart = Cart.query.filter_by(user_id=user.id).first()
    if cart:
        CartItem.query.filter_by(cart_id=cart.id).delete()
        db.session.commit()
    return "", 204


# ------------------------------------------------------------------ orders

def _find_order(user, number):
    order = Order.query.filter_by(number=number).first()
    if order is None or (user.role not in STAFF and order.user_id != user.id):
        raise ApiError(404, "not_found", "No order with that number.")  # 404, not 403: never confirm someone else's order
    return order


@bp.get("/orders")
def orders():
    user = _user()
    query = Order.query if user.role in STAFF else Order.query.filter_by(user_id=user.id)
    status = request.args.get("status")
    if status:
        if status not in OrderStatus.ALL:
            raise ApiError(400, "bad_request", f"status must be one of: {', '.join(OrderStatus.ALL)}.")
        query = query.filter_by(status=status)
    return _page(query.order_by(Order.created_at.desc(), Order.id.desc()), order_json)


def _ship_to(user, data):
    if data.get("address_id") is not None:
        addr = Address.query.filter_by(id=data.get("address_id"), user_id=user.id).first()
        if addr is None:
            raise ApiError(422, "validation_failed", "Choose one of your saved addresses.", {"address_id": "Not one of your addresses."})
        return ShipTo(addr.full_name, addr.phone, addr.one_line())
    a = data.get("address")
    if not isinstance(a, dict):
        raise ApiError(422, "validation_failed", "Say where to deliver.",
                       {"address": "Send address_id, or an address object (full_name, phone, line1, city, region, postal_code)."})
    errors, clean = {}, {}
    for key, max_len, required in (("full_name", 120, True), ("line1", 200, True), ("line2", 200, False),
                                   ("city", 100, True), ("region", 100, True), ("postal_code", 20, True), ("country", 60, False)):
        value = str(a.get(key) or "").strip()
        if required and not value:
            errors[f"address.{key}"] = "Required."
        elif len(value) > max_len:
            errors[f"address.{key}"] = f"At most {max_len} characters."
        clean[key] = value
    try:
        phone = phones.normalize(str(a.get("phone") or ""), str(a.get("phone_country") or "PH").upper())
    except ValueError as exc:
        errors["address.phone"] = str(exc)
    if errors:
        raise ApiError(422, "validation_failed", "Check the delivery address.", errors)
    parts = [clean["line1"], clean["line2"], clean["city"], clean["region"], clean["postal_code"], clean["country"] or "Philippines"]
    return ShipTo(clean["full_name"], phone, ", ".join(p for p in parts if p))


@bp.post("/orders")
def order_create():
    user = _user((ROLE_CUSTOMER,))
    data = _body()
    key = (request.headers.get("Idempotency-Key") or "").strip()[:64] or secrets.token_urlsafe(24)
    existing = Order.query.filter_by(checkout_token=key).first()
    if existing is not None:
        if existing.user_id != user.id:
            raise ApiError(409, "idempotency_conflict", "That Idempotency-Key was already used.")
        return jsonify(order_json(existing, full=True))  # a retry of the same request: same order, 200
    ship_to = _ship_to(user, data)
    notes = str(data.get("notes") or "")[:500]
    code = str(data.get("discount_code") or "").strip().upper() or None
    try:
        order = place_order(user, DEMO_CREDIT, key, code, notes, ship_to)
    except CheckoutError as exc:
        raise ApiError(409, "checkout_failed", str(exc))
    resp = jsonify(order_json(order, full=True))
    resp.status_code = 201
    resp.headers["Location"] = url_for("api.order_detail", number=order.number)
    return resp


@bp.get("/orders/<number>")
def order_detail(number):
    return jsonify(order_json(_find_order(_user(), number), full=True))


@bp.patch("/orders/<number>")
def order_update(number):
    user = _user(STAFF)
    order = _find_order(user, number)
    data = _body()
    status = data.get("status")
    if status not in OrderStatus.ALL:
        raise ApiError(422, "validation_failed", "Choose the new status.", {"status": f"One of: {', '.join(OrderStatus.ALL)}."})
    try:
        change_status(order, status, data.get("reason"))
    except ValueError as exc:
        db.session.rollback()
        raise ApiError(409, "invalid_transition", str(exc))
    audit("order.status", "order", order.id, f"API: {order.number} → {status}", actor=user)
    db.session.commit()
    return jsonify(order_json(order, full=True))


@bp.post("/orders/<number>/cancel")
def order_cancel(number):
    user = _user((ROLE_CUSTOMER,))
    order = _find_order(user, number)
    reason = str(_body().get("reason") or "Cancelled by customer")[:300]
    if not order.customer_can_cancel:
        raise ApiError(409, "cannot_cancel", f"This order is {order.status} and can't be cancelled any more.")
    try:
        change_status(order, OrderStatus.CANCELLED, reason)
    except ValueError as exc:
        db.session.rollback()
        raise ApiError(409, "cannot_cancel", str(exc))
    db.session.commit()
    return jsonify(order_json(order, full=True))


# ------------------------------------------------------------------ outside APIs, through this API

def _upstream_error(exc, service):
    cause = exc.__cause__ or exc
    if isinstance(cause, requests.Timeout):
        return ApiError(504, "upstream_timeout", f"{service} took too long to answer. Try again in a moment.")
    return ApiError(502, "upstream_error", f"{service} isn't answering right now. Try again later.")


@bp.get("/rates")
def rates():
    cfg = current_app.config
    base = cfg["BASE_CURRENCY"]
    out = {}
    for code in cfg["DISPLAY_CURRENCIES"]:
        if code == base:
            continue
        quote = currency.get_quote(code)  # cached; refreshed from Frankfurter when older than FX_CACHE_HOURS
        if quote is not None:
            out[code] = {"rate": str(quote.rate), "date": quote.rate_date, "stale": quote.stale}
    if not out:
        raise ApiError(503, "rates_unavailable", "Exchange rates are unavailable right now. Prices are shown in PHP.",
                       headers={"Retry-After": str(int(cfg["API_RETRY_BACKOFF_MINUTES"]) * 60)})
    return jsonify(base=base, rates=out, source="Frankfurter (European Central Bank reference rates)",
                   note="Display only: orders are always charged in PHP.")


@bp.get("/geocode/reverse")
def geocode_reverse():
    _user()
    try:
        lat, lng = float(request.args["lat"]), float(request.args["lng"])
    except (KeyError, ValueError):
        raise ApiError(400, "bad_request", "Send lat and lng as numbers, e.g. ?lat=13.6218&lng=123.1948.")
    if not (-90 <= lat <= 90 and -180 <= lng <= 180):
        raise ApiError(422, "validation_failed", "Those coordinates are outside the map.", {"lat": "-90 to 90", "lng": "-180 to 180"})
    if mapbox.token():
        try:
            return jsonify(result=mapbox.reverse(lat, lng), source="Mapbox")
        except mapbox.MapboxError:
            pass  # fall back to OpenStreetMap
    try:
        return jsonify(result=nominatim.reverse(lat, lng), source="OpenStreetMap Nominatim")
    except mapbox.MapboxError as exc:
        raise _upstream_error(exc, "The map address service")


# ------------------------------------------------------------------ docs page (HTML), registered on the app

def api_docs():
    return render_template("main/api_docs.html", endpoints=ENDPOINTS)
