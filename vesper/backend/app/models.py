from datetime import datetime, timezone

from sqlalchemy import JSON, CheckConstraint, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def now():
    return datetime.now(timezone.utc)


class Seller(Base):
    __tablename__ = "sellers"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True)
    tagline: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(Text)
    origin: Mapped[str] = mapped_column(String(80))
    founded: Mapped[int] = mapped_column(Integer)
    accent: Mapped[str] = mapped_column(String(9))  # brand colour, hex
    bottle: Mapped[str] = mapped_column(String(20))  # bottle silhouette used by the illustrations
    products: Mapped[list["Product"]] = relationship(back_populates="seller", order_by="Product.id")


class Product(Base):
    __tablename__ = "products"
    __table_args__ = (
        CheckConstraint("stock >= 0", name="stock_not_negative"),
        CheckConstraint("price_centavos > 0", name="price_positive"),
    )
    id: Mapped[str] = mapped_column(String(60), primary_key=True)
    seller_id: Mapped[str] = mapped_column(ForeignKey("sellers.id", ondelete="RESTRICT"), index=True)
    name: Mapped[str] = mapped_column(String(80))
    price_centavos: Mapped[int] = mapped_column(Integer)  # PHP, integer centavos: no float money
    description: Mapped[str] = mapped_column(Text)
    top_notes: Mapped[list] = mapped_column(JSON)
    heart_notes: Mapped[list] = mapped_column(JSON)
    base_notes: Mapped[list] = mapped_column(JSON)
    size_ml: Mapped[int] = mapped_column(Integer)
    family: Mapped[str] = mapped_column(String(20), index=True)
    concentration: Mapped[str] = mapped_column(String(10))
    stock: Mapped[int] = mapped_column(Integer)
    hue: Mapped[str] = mapped_column(String(9))  # juice colour for the bottle illustration
    bestseller: Mapped[bool] = mapped_column(default=False)
    seller: Mapped[Seller] = relationship(back_populates="products")


class Customer(Base):
    __tablename__ = "customers"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(200), index=True)
    phone: Mapped[str] = mapped_column(String(30))
    address: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Cart(Base):
    __tablename__ = "carts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    items: Mapped[list["CartItem"]] = relationship(cascade="all, delete-orphan", order_by="CartItem.id")


class CartItem(Base):
    __tablename__ = "cart_items"
    __table_args__ = (UniqueConstraint("cart_id", "product_id"), CheckConstraint("quantity > 0"))
    id: Mapped[int] = mapped_column(primary_key=True)
    cart_id: Mapped[str] = mapped_column(ForeignKey("carts.id", ondelete="CASCADE"))
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"))
    quantity: Mapped[int] = mapped_column(Integer)
    product: Mapped[Product] = relationship()


class Order(Base):
    __tablename__ = "orders"
    id: Mapped[str] = mapped_column(String(20), primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"))
    cart_id: Mapped[str | None] = mapped_column(String(36))
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending | paid | failed | cancelled
    payment_method: Mapped[str] = mapped_column(String(20))
    subtotal_centavos: Mapped[int] = mapped_column(Integer)
    shipping_centavos: Mapped[int] = mapped_column(Integer)
    total_centavos: Mapped[int] = mapped_column(Integer)
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    customer: Mapped[Customer] = relationship()
    items: Mapped[list["OrderItem"]] = relationship(cascade="all, delete-orphan")
    payment: Mapped["Payment"] = relationship(back_populates="order", uselist=False)


class OrderItem(Base):
    __tablename__ = "order_items"
    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"))
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"))
    name: Mapped[str] = mapped_column(String(80))
    seller_name: Mapped[str] = mapped_column(String(80))
    unit_price_centavos: Mapped[int] = mapped_column(Integer)
    quantity: Mapped[int] = mapped_column(Integer)


class Payment(Base):
    __tablename__ = "payments"
    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id"), unique=True)
    provider: Mapped[str] = mapped_column(String(20))  # paymongo | mock
    status: Mapped[str] = mapped_column(String(20), default="pending")
    amount_centavos: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3), default="PHP")
    checkout_session_id: Mapped[str | None] = mapped_column(String(80), index=True)
    payment_intent_id: Mapped[str | None] = mapped_column(String(80), index=True)
    checkout_url: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)
    order: Mapped[Order] = relationship(back_populates="payment")


class WebhookEvent(Base):
    """Processed PayMongo event ids; the primary key makes redelivery a no-op."""

    __tablename__ = "webhook_events"
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    type: Mapped[str] = mapped_column(String(80))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Subscriber(Base):
    __tablename__ = "subscribers"
    email: Mapped[str] = mapped_column(String(200), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
