from flask import (Blueprint, abort, current_app, flash, jsonify, redirect, render_template, request,
                   send_from_directory, session, url_for)
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from ..extensions import db
from ..forms import NewsletterForm
from ..models import Category, NewsletterSubscription, Product, ProductReview
from ..security import is_safe_redirect
from ..services.catalog import visible_products

bp = Blueprint("main", __name__)

RECENT_KEY = "recently_viewed"


def remember_view(product_id):
    ids = [i for i in session.get(RECENT_KEY, []) if i != product_id]
    session[RECENT_KEY] = ([product_id] + ids)[:10]


def recently_viewed(exclude=None, limit=6):
    ids = [i for i in session.get(RECENT_KEY, []) if i != exclude][:limit]
    if not ids:
        return []
    found = {p.id: p for p in visible_products().filter(Product.id.in_(ids)).all()}
    return [found[i] for i in ids if i in found]


@bp.route("/")
def home():
    base = visible_products()
    featured = base.filter(Product.is_featured.is_(True)).order_by(Product.sold_count.desc()).limit(8).all()
    new_arrivals = base.order_by(Product.created_at.desc(), Product.id.desc()).limit(8).all()
    bestsellers = base.order_by(Product.sold_count.desc()).limit(4).all()
    categories = Category.query.order_by(Category.position).all()
    counts = dict(db.session.query(Product.category_id, db.func.count(Product.id))
                  .filter(Product.status == "active").group_by(Product.category_id).all())
    hero = featured[0] if featured else (new_arrivals[0] if new_arrivals else None)
    review_count = ProductReview.query.filter_by(is_hidden=False).count()
    top_review = (ProductReview.query.filter_by(is_hidden=False, rating=5)
                  .order_by(ProductReview.created_at.desc()).first())
    return render_template("main/home.html", featured=featured, new_arrivals=new_arrivals,
                           bestsellers=bestsellers, categories=categories, counts=counts, hero=hero,
                           recent=recently_viewed(), review_count=review_count, top_review=top_review,
                           newsletter_form=NewsletterForm())


@bp.route("/healthz")
def health():
    try:
        db.session.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False
    return jsonify(status="ok" if db_ok else "degraded", database="ok" if db_ok else "error",
                   app=current_app.config["APP_NAME"]), (200 if db_ok else 503)


@bp.route("/media/<path:filename>")
def media(filename):
    if "/" in filename or "\\" in filename or filename.startswith("."):
        abort(404)
    resp = send_from_directory(current_app.config["UPLOAD_FOLDER"], filename, max_age=60 * 60 * 24 * 30)
    resp.headers["Content-Security-Policy"] = "default-src 'none'"
    return resp


@bp.post("/currency")
def set_currency():
    code = (request.form.get("currency") or "").upper()
    if code in current_app.config["DISPLAY_CURRENCIES"]:
        session["currency"] = code
    dest = request.form.get("next")
    return redirect(dest if is_safe_redirect(dest) else url_for("main.home"))


@bp.post("/newsletter")
def newsletter():
    form = NewsletterForm()
    is_fetch = request.headers.get("X-Requested-With") == "fetch"
    if not form.validate_on_submit():
        msg = (form.email.errors or ["Enter a valid email address."])[0]
        if is_fetch:
            return jsonify(ok=False, error=msg), 400
        flash(msg, "error")
        return redirect(url_for("main.home") + "#newsletter")
    email = form.email.data.lower()
    message = "You're on the list — look out for our next harvest letter."
    if NewsletterSubscription.query.filter_by(email=email).first():
        message = "You're already subscribed. Thank you!"
    else:
        try:
            db.session.add(NewsletterSubscription(email=email))
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
    if is_fetch:
        return jsonify(ok=True, message=message)
    flash(message, "success")
    return redirect(url_for("main.home") + "#newsletter")


PAGES = {
    "about": "Our story",
    "shipping": "Shipping & delivery",
    "returns": "Returns & refunds",
    "privacy": "Privacy policy",
    "terms": "Terms of service",
    "contact": "Contact & support",
    "faq": "Frequently asked questions",
}


@bp.route("/pages/<slug>")
def page(slug):
    if slug not in PAGES:
        abort(404)
    return render_template("main/page.html", slug=slug, title=PAGES[slug], pages=PAGES)
