"""Aggregations for dashboards and reports — all computed from real database records."""
import csv
import io
from datetime import timedelta

from sqlalchemy import func

from ..extensions import db
from ..models import (PRODUCT_ACTIVE, Category, Order, OrderItem, OrderStatus, Product, User,
                      get_int_setting, utcnow)
from ..money import to_major

COUNTED = [s for s in OrderStatus.ALL if s != OrderStatus.CANCELLED]


def revenue_minor(since=None):
    q = db.session.query(func.coalesce(func.sum(Order.total_minor), 0)).filter(Order.status.in_(COUNTED))
    if since:
        q = q.filter(Order.created_at >= since)
    return int(q.scalar() or 0)


def order_count(since=None, statuses=None):
    q = Order.query
    if since:
        q = q.filter(Order.created_at >= since)
    if statuses:
        q = q.filter(Order.status.in_(statuses))
    return q.count()


def daily_revenue(days=14):
    """[(date, revenue_minor, orders)] for the last N days, zero-filled."""
    start = (utcnow() - timedelta(days=days - 1)).replace(hour=0, minute=0, second=0, microsecond=0)
    rows = (db.session.query(func.date(Order.created_at), func.sum(Order.total_minor), func.count(Order.id))
            .filter(Order.created_at >= start, Order.status.in_(COUNTED))
            .group_by(func.date(Order.created_at)).all())
    by_day = {str(d): (int(r or 0), int(c)) for d, r, c in rows}
    out = []
    for i in range(days):
        day = (start + timedelta(days=i)).date()
        rev, cnt = by_day.get(str(day), (0, 0))
        out.append((day, rev, cnt))
    return out


def chart_series(series):
    peak = max((r for _, r, _ in series), default=0) or 1
    return [{"label": d.strftime("%b %d"), "short": d.strftime("%d"), "value": r, "orders": c,
             "pct": round(r / peak * 100, 1)} for d, r, c in series]


def top_products(limit=5):
    return (db.session.query(OrderItem.product_name, OrderItem.product_id,
                             func.sum(OrderItem.quantity).label("units"),
                             func.sum(OrderItem.line_total_minor).label("revenue"))
            .join(Order).filter(Order.status.in_(COUNTED))
            .group_by(OrderItem.product_id, OrderItem.product_name)
            .order_by(func.sum(OrderItem.quantity).desc()).limit(limit).all())


def low_stock(limit=None):
    threshold = get_int_setting("low_stock_threshold")
    q = (Product.query.filter(Product.status == PRODUCT_ACTIVE, Product.stock <= threshold)
         .order_by(Product.stock.asc(), Product.name))
    return q.limit(limit).all() if limit else q.all()


def status_breakdown():
    rows = dict(db.session.query(Order.status, func.count(Order.id)).group_by(Order.status).all())
    return [(s, rows.get(s, 0)) for s in OrderStatus.ALL]


def inventory_by_category():
    return (db.session.query(Category.name, func.count(Product.id), func.coalesce(func.sum(Product.stock), 0),
                             func.coalesce(func.sum(Product.stock * Product.price_minor), 0))
            .outerjoin(Product, (Product.category_id == Category.id) & (Product.status == PRODUCT_ACTIVE))
            .group_by(Category.id).order_by(Category.position).all())


def kpis():
    now = utcnow()
    d30 = now - timedelta(days=30)
    rev30, orders30 = revenue_minor(d30), order_count(d30, COUNTED)
    return {
        "revenue_total": revenue_minor(),
        "revenue_30": rev30,
        "orders_30": orders30,
        "aov_30": rev30 // orders30 if orders30 else 0,
        "customers": User.query.filter_by(role="customer").count(),
        "new_customers_30": User.query.filter(User.role == "customer", User.created_at >= d30).count(),
        "active_products": Product.query.filter_by(status=PRODUCT_ACTIVE).count(),
        "awaiting": order_count(statuses=[OrderStatus.PENDING, OrderStatus.CONFIRMED, OrderStatus.PROCESSING]),
        "low_stock": len(low_stock()),
    }


def _csv(rows, header):
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(header)
    for r in rows:
        # neutralise spreadsheet formula injection
        w.writerow([("'" + v) if isinstance(v, str) and v[:1] in ("=", "+", "-", "@") else v for v in r])
    return buf.getvalue()


def products_csv():
    rows = [(p.sku, p.name, p.brand, p.category.name, str(to_major(p.price_minor)), p.stock, p.status,
             p.sold_count, p.source, p.off_barcode or "", p.created_at.isoformat(timespec="seconds"))
            for p in Product.query.order_by(Product.id).all()]
    return _csv(rows, ["sku", "name", "brand", "category", "price_php", "stock", "status", "units_sold",
                       "source", "barcode", "created_at"])


def orders_csv():
    rows = [(o.number, o.created_at.isoformat(timespec="seconds"), o.user.email, o.status, o.item_count,
             str(to_major(o.subtotal_minor)), str(to_major(o.discount_minor)), str(to_major(o.shipping_minor)),
             str(to_major(o.total_minor)), o.discount_code or "", o.payment.method if o.payment else "",
             o.payment.status if o.payment else "")
            for o in Order.query.order_by(Order.created_at.desc()).all()]
    return _csv(rows, ["order", "created_at", "customer", "status", "items", "subtotal_php", "discount_php",
                       "shipping_php", "total_php", "code", "payment_method", "payment_status"])
