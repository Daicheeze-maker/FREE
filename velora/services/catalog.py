"""Catalog queries and helpers shared by the storefront and staff consoles."""
import re
import secrets

from sqlalchemy import func, or_

from ..extensions import db
from ..models import PRODUCT_ACTIVE, Category, OrderItem, Product, ProductReview

SORTS = {
    "featured": "Featured",
    "newest": "Newest",
    "popular": "Most popular",
    "price_asc": "Price: low to high",
    "price_desc": "Price: high to low",
    "rating": "Top rated",
}


def slugify(text):
    slug = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return slug[:200] or "item"


def unique_slug(name, model=Product, exclude_id=None):
    base = slugify(name)
    slug, n = base, 2
    while True:
        q = model.query.filter_by(slug=slug)
        if exclude_id:
            q = q.filter(model.id != exclude_id)
        if not q.first():
            return slug
        slug, n = f"{base}-{n}", n + 1


def next_sku(prefix="VM"):
    while True:
        sku = f"{prefix}-{secrets.token_hex(3).upper()}"
        if not Product.query.filter_by(sku=sku).first():
            return sku


def visible_products():
    return Product.query.filter(Product.status == PRODUCT_ACTIVE)


def search_products(q=None, category=None, brands=None, min_price=None, max_price=None,
                    availability=None, sort="featured"):
    query = visible_products()
    if q:
        like = f"%{q.strip()[:100]}%"
        query = query.outerjoin(Category).filter(or_(
            Product.name.ilike(like), Product.description.ilike(like),
            Product.short_description.ilike(like), Product.brand.ilike(like),
            Category.name.ilike(like), Product.ingredients.ilike(like),
        ))
    if category:
        query = query.filter(Product.category_id == category.id)
    if brands:
        query = query.filter(Product.brand.in_(brands))
    if min_price is not None:
        query = query.filter(Product.price_minor >= min_price)
    if max_price is not None:
        query = query.filter(Product.price_minor <= max_price)
    if availability == "in_stock":
        query = query.filter(Product.stock > 0)
    if sort == "newest":
        query = query.order_by(Product.created_at.desc(), Product.id.desc())
    elif sort == "popular":
        query = query.order_by(Product.sold_count.desc(), Product.id)
    elif sort == "price_asc":
        query = query.order_by(Product.price_minor.asc(), Product.id)
    elif sort == "price_desc":
        query = query.order_by(Product.price_minor.desc(), Product.id)
    elif sort == "rating":
        avg = (db.session.query(ProductReview.product_id, func.avg(ProductReview.rating).label("avg"))
               .filter(ProductReview.is_hidden.is_(False)).group_by(ProductReview.product_id).subquery())
        query = query.outerjoin(avg, avg.c.product_id == Product.id).order_by(
            func.coalesce(avg.c.avg, 0).desc(), Product.sold_count.desc())
    else:
        query = query.order_by(Product.is_featured.desc(), Product.sold_count.desc(), Product.id)
    return query


def related_products(product, limit=4):
    return (visible_products().filter(Product.category_id == product.category_id, Product.id != product.id)
            .order_by(Product.sold_count.desc()).limit(limit).all())


def all_brands():
    rows = (db.session.query(Product.brand).filter(Product.status == PRODUCT_ACTIVE)
            .distinct().order_by(Product.brand).all())
    return [r[0] for r in rows]


def has_purchased(user, product):
    """A customer may review only products from a delivered order."""
    from ..models import Order, OrderStatus
    return db.session.query(OrderItem.id).join(Order).filter(
        Order.user_id == user.id, Order.status == OrderStatus.DELIVERED,
        OrderItem.product_id == product.id).first() is not None
