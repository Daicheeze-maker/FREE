from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy.exc import IntegrityError

from ..extensions import db
from ..forms import ReviewForm
from ..models import PRODUCT_ACTIVE, Category, Product, ProductReview
from ..money import to_minor
from ..services.catalog import SORTS, all_brands, has_purchased, related_products, search_products
from .main import recently_viewed, remember_view

bp = Blueprint("catalog", __name__, url_prefix="/shop")


def _price_arg(name):
    raw = request.args.get(name, "").strip()
    if not raw:
        return None
    try:
        return to_minor(raw)
    except ValueError:
        return None


@bp.route("/")
@bp.route("/c/<slug>")
def listing(slug=None):
    category = None
    if slug:
        category = Category.query.filter_by(slug=slug).first_or_404()
    q = request.args.get("q", "").strip()[:100]
    sort = request.args.get("sort", "featured")
    if sort not in SORTS:
        sort = "featured"
    brands = [b for b in request.args.getlist("brand") if b][:20]
    availability = request.args.get("availability")
    min_price, max_price = _price_arg("min"), _price_arg("max")
    page = request.args.get("page", 1, type=int)
    query = search_products(q=q, category=category, brands=brands, min_price=min_price, max_price=max_price,
                            availability=availability, sort=sort)
    pagination = query.paginate(page=max(page, 1), per_page=current_app.config["PRODUCTS_PER_PAGE"], error_out=False)
    args = request.args.to_dict(flat=False)
    args.pop("page", None)
    active_filters = bool(q or brands or availability or min_price is not None or max_price is not None)
    tmpl = "catalog/_results.html" if request.headers.get("X-Requested-With") == "fetch" else "catalog/listing.html"
    return render_template(tmpl, products=pagination.items, pagination=pagination, category=category,
                           q=q, sort=sort, sorts=SORTS, brands=all_brands(), selected_brands=brands,
                           availability=availability, min_price=request.args.get("min", ""),
                           max_price=request.args.get("max", ""), args=args, active_filters=active_filters,
                           args_no_q={k: v for k, v in args.items() if k != "q"})


@bp.route("/p/<slug>")
def detail(slug):
    product = Product.query.filter_by(slug=slug).first_or_404()
    staff = current_user.is_authenticated and current_user.is_staff
    if product.status != PRODUCT_ACTIVE and not staff:
        abort(404)
    remember_view(product.id)
    can_review = already_reviewed = False
    form = None
    if current_user.is_authenticated and current_user.role == "customer":
        already_reviewed = ProductReview.query.filter_by(user_id=current_user.id, product_id=product.id).first() is not None
        can_review = not already_reviewed and has_purchased(current_user, product)
        form = ReviewForm() if can_review else None
    reviews = product.visible_reviews
    dist = {i: sum(1 for r in reviews if r.rating == i) for i in range(1, 6)}
    return render_template("catalog/detail.html", product=product, related=related_products(product),
                           recent=recently_viewed(exclude=product.id, limit=4), reviews=reviews, dist=dist,
                           can_review=can_review, already_reviewed=already_reviewed, review_form=form)


@bp.post("/p/<slug>/review")
@login_required
def review(slug):
    product = Product.query.filter_by(slug=slug, status=PRODUCT_ACTIVE).first_or_404()
    if current_user.role != "customer":
        abort(403)
    if ProductReview.query.filter_by(user_id=current_user.id, product_id=product.id).first():
        flash("You've already reviewed this product.", "info")
        return redirect(url_for("catalog.detail", slug=slug) + "#reviews")
    if not has_purchased(current_user, product):
        flash("You can review products once your order has been delivered.", "error")
        return redirect(url_for("catalog.detail", slug=slug) + "#reviews")
    form = ReviewForm()
    if not form.validate_on_submit():
        for errs in form.errors.values():
            flash(errs[0], "error")
            break
        return redirect(url_for("catalog.detail", slug=slug) + "#write-review")
    try:
        db.session.add(ProductReview(product_id=product.id, user_id=current_user.id, rating=int(form.rating.data),
                                     title=form.title.data, body=form.body.data))
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        flash("You've already reviewed this product.", "info")
        return redirect(url_for("catalog.detail", slug=slug) + "#reviews")
    flash("Thanks — your review is live.", "success")
    return redirect(url_for("catalog.detail", slug=slug) + "#reviews")
