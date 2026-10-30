"""Relational schema. Monetary values are integer minor units of the base currency (PHP)."""
from datetime import datetime, timezone

from flask_login import UserMixin
from sqlalchemy import CheckConstraint, Index, UniqueConstraint, func
from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import db


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class TimestampMixin:
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow, index=True)
    updated_at = db.Column(db.DateTime, nullable=False, default=utcnow, onupdate=utcnow)


# ---------------------------------------------------------------- users ----

ROLE_CUSTOMER, ROLE_SELLER, ROLE_ADMIN = "customer", "seller", "admin"
ROLES = (ROLE_CUSTOMER, ROLE_SELLER, ROLE_ADMIN)


class User(UserMixin, TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), nullable=False, unique=True, index=True)
    full_name = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(40))
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default=ROLE_CUSTOMER)
    is_active_account = db.Column(db.Boolean, nullable=False, default=True)
    failed_login_count = db.Column(db.Integer, nullable=False, default=0)
    locked_until = db.Column(db.DateTime)
    last_login_at = db.Column(db.DateTime)

    addresses = db.relationship("Address", back_populates="user", cascade="all, delete-orphan",
                                order_by="Address.is_default.desc()")
    orders = db.relationship("Order", back_populates="user", order_by="Order.created_at.desc()")
    wishlist_items = db.relationship("WishlistItem", back_populates="user", cascade="all, delete-orphan")
    notifications = db.relationship("Notification", back_populates="user", cascade="all, delete-orphan",
                                    order_by="Notification.created_at.desc()")

    __table_args__ = (CheckConstraint(f"role IN {ROLES}", name="valid_role"),)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def is_active(self):  # Flask-Login: disabled accounts cannot authenticate
        return bool(self.is_active_account)

    @property
    def first_name(self):
        return (self.full_name or "").split(" ")[0]

    @property
    def is_admin(self):
        return self.role == ROLE_ADMIN

    @property
    def is_seller(self):
        return self.role == ROLE_SELLER

    @property
    def is_staff(self):
        return self.role in (ROLE_SELLER, ROLE_ADMIN)

    @property
    def unread_notifications(self):
        return Notification.query.filter_by(user_id=self.id, is_read=False).count()


class Address(TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True)
    label = db.Column(db.String(40), nullable=False, default="Home")
    full_name = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(40), nullable=False)
    line1 = db.Column(db.String(200), nullable=False)
    line2 = db.Column(db.String(200))
    city = db.Column(db.String(100), nullable=False)
    region = db.Column(db.String(100), nullable=False)
    postal_code = db.Column(db.String(20), nullable=False)
    country = db.Column(db.String(60), nullable=False, default="Philippines")
    is_default = db.Column(db.Boolean, nullable=False, default=False)

    user = db.relationship("User", back_populates="addresses")

    def one_line(self):
        parts = [self.line1, self.line2, self.city, self.region, self.postal_code, self.country]
        return ", ".join(p for p in parts if p)


# -------------------------------------------------------------- catalog ----

class Category(TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False, unique=True)
    slug = db.Column(db.String(90), nullable=False, unique=True, index=True)
    description = db.Column(db.String(300))
    icon = db.Column(db.String(40), nullable=False, default="package")
    position = db.Column(db.Integer, nullable=False, default=0)

    products = db.relationship("Product", back_populates="category")


PRODUCT_ACTIVE, PRODUCT_DRAFT, PRODUCT_ARCHIVED = "active", "draft", "archived"
PRODUCT_STATUSES = (PRODUCT_ACTIVE, PRODUCT_DRAFT, PRODUCT_ARCHIVED)


class Product(TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    slug = db.Column(db.String(220), nullable=False, unique=True, index=True)
    sku = db.Column(db.String(64), nullable=False, unique=True)
    brand = db.Column(db.String(120), nullable=False, default="Velora", index=True)
    category_id = db.Column(db.Integer, db.ForeignKey("category.id", ondelete="RESTRICT"), nullable=False, index=True)
    short_description = db.Column(db.String(300), nullable=False, default="")
    description = db.Column(db.Text, nullable=False, default="")
    price_minor = db.Column(db.Integer, nullable=False)
    compare_at_minor = db.Column(db.Integer)
    stock = db.Column(db.Integer, nullable=False, default=0)
    status = db.Column(db.String(20), nullable=False, default=PRODUCT_ACTIVE, index=True)
    is_featured = db.Column(db.Boolean, nullable=False, default=False)
    sold_count = db.Column(db.Integer, nullable=False, default=0)
    size_label = db.Column(db.String(60))
    origin = db.Column(db.String(120))

    # Open Food Facts enrichment
    source = db.Column(db.String(30), nullable=False, default="manual")
    off_barcode = db.Column(db.String(32), unique=True)
    ingredients = db.Column(db.Text)
    allergens = db.Column(db.String(300))
    nutriscore = db.Column(db.String(2))
    nutrition_json = db.Column(db.JSON)
    off_categories = db.Column(db.String(400))
    synced_at = db.Column(db.DateTime)

    category = db.relationship("Category", back_populates="products")
    images = db.relationship("ProductImage", back_populates="product", cascade="all, delete-orphan",
                             order_by="ProductImage.position")
    reviews = db.relationship("ProductReview", back_populates="product", cascade="all, delete-orphan",
                              order_by="ProductReview.created_at.desc()")

    __table_args__ = (
        CheckConstraint("price_minor >= 0", name="price_non_negative"),
        CheckConstraint("stock >= 0", name="stock_non_negative"),
        CheckConstraint(f"status IN {PRODUCT_STATUSES}", name="valid_status"),
        Index("ix_product_status_created", "status", "created_at"),
    )

    @property
    def primary_image(self):
        return self.images[0] if self.images else None

    @property
    def in_stock(self):
        return self.stock > 0

    @property
    def stock_label(self):
        if self.stock <= 0:
            return "Sold out"
        if self.stock <= 5:
            return f"Only {self.stock} left"
        return "In stock"

    @property
    def stock_state(self):
        if self.stock <= 0:
            return "out"
        return "low" if self.stock <= 5 else "ok"

    @property
    def visible_reviews(self):
        return [r for r in self.reviews if not r.is_hidden]

    @property
    def rating(self):
        rs = self.visible_reviews
        return round(sum(r.rating for r in rs) / len(rs), 1) if rs else None

    @property
    def is_new(self):
        return (utcnow() - self.created_at).days <= 21


class ProductImage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("product.id", ondelete="CASCADE"), nullable=False, index=True)
    url = db.Column(db.String(500))         # remote (e.g. Unsplash / Open Food Facts)
    filename = db.Column(db.String(200))    # local upload stored in UPLOAD_FOLDER
    alt = db.Column(db.String(200), nullable=False, default="")
    position = db.Column(db.Integer, nullable=False, default=0)
    credit = db.Column(db.String(200))

    product = db.relationship("Product", back_populates="images")


# ----------------------------------------------------- cart & wishlist ----

class Cart(TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="CASCADE"), nullable=False, unique=True)
    items = db.relationship("CartItem", back_populates="cart", cascade="all, delete-orphan")


class CartItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    cart_id = db.Column(db.Integer, db.ForeignKey("cart.id", ondelete="CASCADE"), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey("product.id", ondelete="CASCADE"), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=1)

    cart = db.relationship("Cart", back_populates="items")
    product = db.relationship("Product")
    __table_args__ = (
        UniqueConstraint("cart_id", "product_id", name="uq_cart_item_product"),
        CheckConstraint("quantity > 0", name="quantity_positive"),
    )


class WishlistItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey("product.id", ondelete="CASCADE"), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    user = db.relationship("User", back_populates="wishlist_items")
    product = db.relationship("Product")
    __table_args__ = (UniqueConstraint("user_id", "product_id", name="uq_wishlist_user_product"),)


# --------------------------------------------------------------- orders ----

class OrderStatus:
    PENDING = "pending"
    CONFIRMED = "confirmed"
    PROCESSING = "processing"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"

    ALL = (PENDING, CONFIRMED, PROCESSING, SHIPPED, DELIVERED, CANCELLED)
    FLOW = (PENDING, CONFIRMED, PROCESSING, SHIPPED, DELIVERED)
    TRANSITIONS = {
        PENDING: {CONFIRMED, CANCELLED},
        CONFIRMED: {PROCESSING, CANCELLED},
        PROCESSING: {SHIPPED, CANCELLED},
        SHIPPED: {DELIVERED},
        DELIVERED: set(),
        CANCELLED: set(),
    }
    CUSTOMER_CANCELLABLE = {PENDING, CONFIRMED}

    @classmethod
    def can_transition(cls, current, new):
        return new in cls.TRANSITIONS.get(current, set())


class Order(TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    number = db.Column(db.String(20), nullable=False, unique=True, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="RESTRICT"), nullable=False, index=True)
    status = db.Column(db.String(20), nullable=False, default=OrderStatus.PENDING, index=True)
    checkout_token = db.Column(db.String(64), nullable=False, unique=True)

    subtotal_minor = db.Column(db.Integer, nullable=False)
    discount_minor = db.Column(db.Integer, nullable=False, default=0)
    shipping_minor = db.Column(db.Integer, nullable=False, default=0)
    total_minor = db.Column(db.Integer, nullable=False)
    currency = db.Column(db.String(3), nullable=False, default="PHP")
    discount_code = db.Column(db.String(40))

    # Address snapshot
    ship_name = db.Column(db.String(120), nullable=False)
    ship_phone = db.Column(db.String(40), nullable=False)
    ship_address = db.Column(db.String(600), nullable=False)
    notes = db.Column(db.String(500))

    confirmed_at = db.Column(db.DateTime)
    shipped_at = db.Column(db.DateTime)
    delivered_at = db.Column(db.DateTime)
    cancelled_at = db.Column(db.DateTime)
    cancel_reason = db.Column(db.String(300))

    user = db.relationship("User", back_populates="orders")
    items = db.relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")
    payments = db.relationship("PaymentRecord", back_populates="order", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint(f"status IN {OrderStatus.ALL}", name="valid_status"),
        CheckConstraint("total_minor >= 0", name="total_non_negative"),
    )

    @property
    def item_count(self):
        return sum(i.quantity for i in self.items)

    @property
    def customer_can_cancel(self):
        return self.status in OrderStatus.CUSTOMER_CANCELLABLE

    @property
    def next_statuses(self):
        return [s for s in OrderStatus.ALL if OrderStatus.can_transition(self.status, s)]

    @property
    def payment(self):
        return self.payments[-1] if self.payments else None


class OrderItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("order.id", ondelete="CASCADE"), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey("product.id", ondelete="SET NULL"), index=True)
    # Snapshot so history never changes when the catalog does
    product_name = db.Column(db.String(200), nullable=False)
    product_sku = db.Column(db.String(64), nullable=False)
    product_brand = db.Column(db.String(120))
    image_url = db.Column(db.String(500))
    unit_price_minor = db.Column(db.Integer, nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    discount_minor = db.Column(db.Integer, nullable=False, default=0)
    line_total_minor = db.Column(db.Integer, nullable=False)

    order = db.relationship("Order", back_populates="items")
    product = db.relationship("Product")
    __table_args__ = (CheckConstraint("quantity > 0", name="quantity_positive"),)


class PaymentRecord(TimestampMixin, db.Model):
    """Simulated payment. No card data is ever collected or stored."""
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("order.id", ondelete="CASCADE"), nullable=False, index=True)
    provider = db.Column(db.String(40), nullable=False)
    method = db.Column(db.String(40), nullable=False)
    status = db.Column(db.String(20), nullable=False)  # succeeded / pending / failed / refunded
    amount_minor = db.Column(db.Integer, nullable=False)
    currency = db.Column(db.String(3), nullable=False)
    reference = db.Column(db.String(64), nullable=False, unique=True)
    message = db.Column(db.String(300))

    order = db.relationship("Order", back_populates="payments")


# ------------------------------------------------------ reviews/promos ----

class ProductReview(TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("product.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True)
    rating = db.Column(db.Integer, nullable=False)
    title = db.Column(db.String(120), nullable=False)
    body = db.Column(db.Text, nullable=False)
    is_hidden = db.Column(db.Boolean, nullable=False, default=False)
    staff_reply = db.Column(db.Text)

    product = db.relationship("Product", back_populates="reviews")
    user = db.relationship("User")
    __table_args__ = (
        UniqueConstraint("user_id", "product_id", name="uq_review_user_product"),
        CheckConstraint("rating BETWEEN 1 AND 5", name="rating_range"),
    )


class DiscountCode(TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(40), nullable=False, unique=True, index=True)
    description = db.Column(db.String(200), nullable=False, default="")
    kind = db.Column(db.String(10), nullable=False, default="percent")  # percent | fixed
    value = db.Column(db.Integer, nullable=False)  # percent (1-90) or minor units
    min_subtotal_minor = db.Column(db.Integer, nullable=False, default=0)
    max_uses = db.Column(db.Integer)
    used_count = db.Column(db.Integer, nullable=False, default=0)
    starts_at = db.Column(db.DateTime)
    ends_at = db.Column(db.DateTime)
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    __table_args__ = (
        CheckConstraint("kind IN ('percent', 'fixed')", name="valid_kind"),
        CheckConstraint("value > 0", name="value_positive"),
    )


class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True)
    title = db.Column(db.String(140), nullable=False)
    body = db.Column(db.String(400), nullable=False, default="")
    link = db.Column(db.String(300))
    icon = db.Column(db.String(40), nullable=False, default="bell")
    is_read = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow, index=True)

    user = db.relationship("User", back_populates="notifications")


# ----------------------------------------------------------- platform ----

class ExchangeRateCache(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    base = db.Column(db.String(3), nullable=False)
    target = db.Column(db.String(3), nullable=False)
    rate = db.Column(db.String(32), nullable=False)  # Decimal stored as text, never float
    rate_date = db.Column(db.String(10))             # date published by the provider
    fetched_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    __table_args__ = (UniqueConstraint("base", "target", name="uq_fx_pair"),)


class ApiStatus(db.Model):
    """Health/sync bookkeeping per external API."""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(40), nullable=False, unique=True)
    last_success_at = db.Column(db.DateTime)
    last_error_at = db.Column(db.DateTime)
    last_error = db.Column(db.String(500))
    success_count = db.Column(db.Integer, nullable=False, default=0)
    error_count = db.Column(db.Integer, nullable=False, default=0)
    last_latency_ms = db.Column(db.Integer)

    @property
    def healthy(self):
        if not self.last_success_at:
            return False
        return not self.last_error_at or self.last_success_at >= self.last_error_at


class AuditLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    actor_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="SET NULL"), index=True)
    action = db.Column(db.String(60), nullable=False, index=True)
    target_type = db.Column(db.String(40))
    target_id = db.Column(db.String(40))
    details = db.Column(db.String(800))
    ip_address = db.Column(db.String(64))
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow, index=True)

    actor = db.relationship("User")


class NewsletterSubscription(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), nullable=False, unique=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)


class StoreSetting(db.Model):
    key = db.Column(db.String(60), primary_key=True)
    value = db.Column(db.String(500), nullable=False)
    updated_at = db.Column(db.DateTime, nullable=False, default=utcnow, onupdate=utcnow)


DEFAULT_SETTINGS = {
    "shipping_flat_minor": "15000",          # ₱150.00
    "free_shipping_threshold_minor": "250000",  # ₱2,500.00
    "low_stock_threshold": "8",
    "store_announcement": "Free delivery on orders over ₱2,500 · 30-day free returns on clothing & accessories",
    "support_email": "care@veloramarket.example",
}


def get_setting(key):
    row = db.session.get(StoreSetting, key)
    return row.value if row else DEFAULT_SETTINGS.get(key)


def get_int_setting(key):
    try:
        return int(get_setting(key))
    except (TypeError, ValueError):
        return int(DEFAULT_SETTINGS[key])


__all__ = [n for n in dir() if not n.startswith("_")] + ["func"]
