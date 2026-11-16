"""Store-manager console: catalog, fulfillment, promotions, feedback, Open Food Facts import.

Sellers and administrators can both use these tools. This is a single-store catalog,
not a multi-vendor marketplace.
"""
import re
from datetime import timedelta

from flask import Blueprint, Response, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError

from ..extensions import db
from ..forms import (CategoryForm, DiscountForm, OFFImportForm, OFFSearchForm, OrderStatusForm, ProductForm,
                     StaffReplyForm)
from ..models import (PRODUCT_ACTIVE, PRODUCT_ARCHIVED, PRODUCT_DRAFT, PRODUCT_STATUSES, Category, DiscountCode,
                      Order, OrderStatus, Product, ProductImage, ProductReview, StoreSetting, utcnow)
from ..photos import SLOTS, credit_key, product_query, setting_key
from ..money import to_major
from ..security import audit, roles_required
from ..services import openfoodfacts as off
from ..services import pexels, photo_check, photo_fill
from ..services.photo_fill import apply_photo as _apply_photo, pick_photo as _pick_photo
from ..services import reports
from ..services.catalog import next_sku, slugify, unique_slug
from ..services.orders import change_status
from ..services.uploads import UploadError, delete_upload, save_image_bytes, save_product_image

bp = Blueprint("seller", __name__, url_prefix="/seller")
staff = roles_required("seller", "admin")


@bp.before_request
@staff
def _guard():
    return None


@bp.route("/")
def dashboard():
    now = utcnow()
    series = reports.chart_series(reports.daily_revenue(14))
    queue = (Order.query.filter(Order.status.in_([OrderStatus.PENDING, OrderStatus.CONFIRMED, OrderStatus.PROCESSING]))
             .order_by(Order.created_at.asc()).limit(6).all())
    recent_reviews = ProductReview.query.order_by(ProductReview.created_at.desc()).limit(4).all()
    return render_template("seller/dashboard.html", k=reports.kpis(), series=series,
                           rev14=sum(s["value"] for s in series), top=reports.top_products(5),
                           low=reports.low_stock(6), queue=queue, breakdown=reports.status_breakdown(),
                           reviews=recent_reviews, today=now)


# ---------------------------------------------------------------- products

@bp.route("/products")
def products():
    q = request.args.get("q", "").strip()[:100]
    status = request.args.get("status", "")
    cat = request.args.get("category", type=int)
    query = Product.query
    if q:
        like = f"%{q}%"
        query = query.filter(or_(Product.name.ilike(like), Product.sku.ilike(like), Product.brand.ilike(like)))
    if status in PRODUCT_STATUSES:
        query = query.filter_by(status=status)
    if cat:
        query = query.filter_by(category_id=cat)
    if request.args.get("nophoto"):
        query = query.filter(~Product.images.any())
    if request.args.get("low"):
        from ..models import get_int_setting
        query = query.filter(Product.stock <= get_int_setting("low_stock_threshold"), Product.status == PRODUCT_ACTIVE)
    page = request.args.get("page", 1, type=int)
    pagination = query.order_by(Product.updated_at.desc()).paginate(page=max(page, 1), per_page=20, error_out=False)
    no_photo = Product.query.filter(Product.status != PRODUCT_ARCHIVED, ~Product.images.any()).count()
    return render_template("seller/products.html", pagination=pagination, q=q, status=status, cat=cat, no_photo=no_photo,
                           pexels_ready=bool(pexels.api_key()),
                           categories=Category.query.order_by(Category.position).all(), statuses=PRODUCT_STATUSES)


def _product_form(product=None):
    form = ProductForm(obj=product)
    form.category_id.choices = [(c.id, c.name) for c in Category.query.order_by(Category.position)]
    if product is not None and request.method == "GET":
        form.price.data = str(to_major(product.price_minor))
        form.compare_at.data = str(to_major(product.compare_at_minor)) if product.compare_at_minor else ""
    return form


def _apply_product_form(form, product):
    product.name = form.name.data
    product.brand = form.brand.data
    product.category_id = form.category_id.data
    product.short_description = form.short_description.data
    product.description = form.description.data
    product.price_minor = form.price.minor
    product.compare_at_minor = form.compare_at.minor
    product.stock = form.stock.data
    product.size_label = form.size_label.data or None
    product.sizes = form.sizes.data or None
    product.origin = form.origin.data or None
    product.ingredients = form.ingredients.data or None
    product.status = form.status.data
    product.is_featured = form.is_featured.data


def _attach_image(form, product):
    added = []
    upload = request.files.get(form.image.name)
    if upload and upload.filename:
        added.append(ProductImage(filename=save_product_image(upload), alt=product.name))
    if form.image_url.data:
        added.append(ProductImage(url=form.image_url.data, alt=product.name))
    if not added:
        return
    existing = list(product.images)
    ordered = added + existing if form.make_cover.data else existing + added
    for img in added:
        product.images.append(img)
    for pos, img in enumerate(ordered):
        img.position = pos
    product.images.sort(key=lambda i: i.position)


@bp.route("/products/new", methods=["GET", "POST"])
def product_new():
    form = _product_form()
    if request.method == "GET":
        form.status.data = PRODUCT_ACTIVE
    if form.validate_on_submit():
        product = Product(slug=unique_slug(form.name.data), sku=next_sku())
        _apply_product_form(form, product)
        try:
            _attach_image(form, product)
        except UploadError as exc:
            form.image.errors.append(str(exc))
            return render_template("seller/product_form.html", form=form, product=None), 400
        db.session.add(product)
        db.session.flush()
        audit("product.create", "product", product.id, product.name)
        db.session.commit()
        flash(f"Created {product.name}.", "success")
        return redirect(url_for("seller.product_edit", product_id=product.id))
    return render_template("seller/product_form.html", form=form, product=None)


@bp.route("/products/<int:product_id>", methods=["GET", "POST"])
def product_edit(product_id):
    product = db.session.get(Product, product_id) or abort(404)
    form = _product_form(product)
    if form.validate_on_submit():
        old_price, old_stock = product.price_minor, product.stock
        if form.name.data != product.name:
            product.slug = unique_slug(form.name.data, exclude_id=product.id)
        _apply_product_form(form, product)
        try:
            _attach_image(form, product)
        except UploadError as exc:
            db.session.rollback()
            form.image.errors.append(str(exc))
            return render_template("seller/product_form.html", form=form, product=product), 400
        changes = []
        if old_price != product.price_minor:
            changes.append(f"price {to_major(old_price)}→{to_major(product.price_minor)}")
        if old_stock != product.stock:
            changes.append(f"stock {old_stock}→{product.stock}")
        audit("product.update", "product", product.id, f"{product.name} {'; '.join(changes)}".strip())
        db.session.commit()
        flash("Product saved.", "success")
        return redirect(url_for("seller.product_edit", product_id=product.id))
    return render_template("seller/product_form.html", form=form, product=product)


@bp.post("/products/<int:product_id>/status/<status>")
def product_status(product_id, status):
    product = db.session.get(Product, product_id) or abort(404)
    if status not in PRODUCT_STATUSES:
        abort(400)
    product.status = status
    audit(f"product.{ 'archive' if status == PRODUCT_ARCHIVED else 'status' }", "product", product.id,
          f"{product.name} → {status}")
    db.session.commit()
    flash(f"{product.name} is now {status}.", "success")
    return redirect(request.referrer or url_for("seller.products"))


@bp.post("/products/<int:product_id>/images/<int:image_id>/delete")
def image_delete(product_id, image_id):
    img = db.session.get(ProductImage, image_id)
    if img is None or img.product_id != product_id:
        abort(404)
    delete_upload(img.filename)
    db.session.delete(img)
    db.session.commit()
    flash("Image removed.", "info")
    return redirect(url_for("seller.product_edit", product_id=product_id))


@bp.post("/products/<int:product_id>/images/<int:image_id>/primary")
def image_primary(product_id, image_id):
    product = db.session.get(Product, product_id) or abort(404)
    ordered = sorted(product.images, key=lambda i: (i.id != image_id, i.position))
    for pos, img in enumerate(ordered):
        img.position = pos
    db.session.commit()
    flash("Cover image updated.", "success")
    return redirect(url_for("seller.product_edit", product_id=product_id))


@bp.route("/inventory")
def inventory():
    return render_template("seller/inventory.html", low=reports.low_stock(),
                           by_cat=reports.inventory_by_category())


@bp.post("/inventory/<int:product_id>")
def restock(product_id):
    product = db.session.get(Product, product_id) or abort(404)
    qty = request.form.get("add", type=int)
    if qty is None or not 1 <= qty <= 10000:
        flash("Enter a restock quantity between 1 and 10,000.", "error")
    else:
        product.stock += qty
        audit("inventory.restock", "product", product.id, f"+{qty} → {product.stock}")
        db.session.commit()
        flash(f"Added {qty} units to {product.name}.", "success")
    return redirect(request.referrer or url_for("seller.inventory"))


# -------------------------------------------------------------- categories

@bp.route("/categories", methods=["GET", "POST"])
def categories():
    form = CategoryForm()
    if form.validate_on_submit():
        if Category.query.filter(db.func.lower(Category.name) == form.name.data.lower()).first():
            form.name.errors.append("A category with this name exists.")
        else:
            cat = Category(name=form.name.data, slug=unique_slug(form.name.data, Category),
                           description=form.description.data, icon=form.icon.data, position=form.position.data)
            db.session.add(cat)
            audit("category.create", "category", None, cat.name)
            db.session.commit()
            flash("Category created.", "success")
            return redirect(url_for("seller.categories"))
    cats = Category.query.order_by(Category.position).all()
    counts = dict(db.session.query(Product.category_id, db.func.count(Product.id)).group_by(Product.category_id).all())
    return render_template("seller/categories.html", form=form, categories=cats, counts=counts)


@bp.route("/categories/<int:cat_id>", methods=["GET", "POST"])
def category_edit(cat_id):
    cat = db.session.get(Category, cat_id) or abort(404)
    form = CategoryForm(obj=cat)
    if form.validate_on_submit():
        clash = Category.query.filter(db.func.lower(Category.name) == form.name.data.lower(), Category.id != cat.id).first()
        if clash:
            form.name.errors.append("A category with this name exists.")
        else:
            form.populate_obj(cat)
            cat.slug = unique_slug(cat.name, Category, exclude_id=cat.id)
            audit("category.update", "category", cat.id, cat.name)
            db.session.commit()
            flash("Category saved.", "success")
            return redirect(url_for("seller.categories"))
    return render_template("seller/category_edit.html", form=form, category=cat)


@bp.post("/categories/<int:cat_id>/delete")
def category_delete(cat_id):
    cat = db.session.get(Category, cat_id) or abort(404)
    if Product.query.filter_by(category_id=cat.id).count():
        flash("Move or archive this category's products before deleting it.", "error")
    else:
        audit("category.delete", "category", cat.id, cat.name)
        db.session.delete(cat)
        db.session.commit()
        flash("Category deleted.", "info")
    return redirect(url_for("seller.categories"))


# ------------------------------------------------------------------ orders

@bp.route("/orders")
def orders():
    status = request.args.get("status", "")
    q = request.args.get("q", "").strip()[:60]
    query = Order.query
    if status in OrderStatus.ALL:
        query = query.filter_by(status=status)
    if q:
        from ..models import User
        query = query.join(Order.user).filter(or_(Order.number.ilike(f"%{q}%"), User.email.ilike(f"%{q}%"),
                                                  Order.ship_name.ilike(f"%{q}%")))
    page = request.args.get("page", 1, type=int)
    pagination = query.order_by(Order.created_at.desc()).paginate(page=max(page, 1), per_page=20, error_out=False)
    return render_template("seller/orders.html", pagination=pagination, status=status, q=q,
                           breakdown=reports.status_breakdown())


@bp.route("/orders/<number>", methods=["GET", "POST"])
def order_detail(number):
    order = Order.query.filter_by(number=number).first_or_404()
    form = OrderStatusForm()
    form.status.choices = [(s, s.title()) for s in order.next_statuses]
    if form.validate_on_submit():
        old = order.status
        try:
            change_status(order, form.status.data, form.reason.data)
        except ValueError as exc:
            flash(str(exc), "error")
        else:
            audit("order.status", "order", order.number, f"{old} → {order.status}")
            db.session.commit()
            flash(f"Order {order.number} marked {order.status}.", "success")
        return redirect(url_for("seller.order_detail", number=number))
    return render_template("seller/order_detail.html", order=order, form=form, flow=OrderStatus.FLOW)


# --------------------------------------------------------------- discounts

@bp.route("/discounts")
def discounts():
    return render_template("seller/discounts.html", discounts=DiscountCode.query.order_by(DiscountCode.created_at.desc()).all(),
                           now=utcnow())


@bp.route("/discounts/new", methods=["GET", "POST"])
@bp.route("/discounts/<int:discount_id>", methods=["GET", "POST"])
def discount_form(discount_id=None):
    discount = db.session.get(DiscountCode, discount_id) if discount_id else None
    if discount_id and discount is None:
        abort(404)
    form = DiscountForm(obj=discount)
    if request.method == "GET" and discount:
        form.value.data = str(discount.value) if discount.kind == "percent" else str(to_major(discount.value))
        form.min_subtotal.data = str(to_major(discount.min_subtotal_minor)) if discount.min_subtotal_minor else ""
    if form.validate_on_submit():
        code = form.code.data.upper()
        clash = DiscountCode.query.filter(DiscountCode.code == code)
        if discount:
            clash = clash.filter(DiscountCode.id != discount.id)
        if clash.first():
            form.code.errors.append("That code already exists.")
        else:
            d = discount or DiscountCode()
            d.code, d.description, d.kind, d.value = code, form.description.data or "", form.kind.data, form.value_int
            d.min_subtotal_minor = form.min_subtotal.minor or 0
            d.max_uses, d.starts_at, d.ends_at = form.max_uses.data, form.starts_at.data, form.ends_at.data
            d.is_active = form.is_active.data
            if not discount:
                db.session.add(d)
            audit("discount.update" if discount else "discount.create", "discount", code,
                  f"{d.kind} {d.value} active={d.is_active}")
            db.session.commit()
            flash(f"Discount {code} saved.", "success")
            return redirect(url_for("seller.discounts"))
    return render_template("seller/discount_form.html", form=form, discount=discount)


@bp.post("/discounts/<int:discount_id>/toggle")
def discount_toggle(discount_id):
    d = db.session.get(DiscountCode, discount_id) or abort(404)
    d.is_active = not d.is_active
    audit("discount.toggle", "discount", d.code, f"active={d.is_active}")
    db.session.commit()
    flash(f"{d.code} {'activated' if d.is_active else 'paused'}.", "success")
    return redirect(url_for("seller.discounts"))


# ----------------------------------------------------------------- reviews

@bp.route("/reviews")
def reviews():
    rating = request.args.get("rating", type=int)
    q = ProductReview.query
    if rating in range(1, 6):
        q = q.filter_by(rating=rating)
    items = q.order_by(ProductReview.created_at.desc()).limit(200).all()
    avg = db.session.query(db.func.avg(ProductReview.rating)).filter(ProductReview.is_hidden.is_(False)).scalar()
    return render_template("seller/reviews.html", reviews=items, rating=rating, avg=round(avg or 0, 2),
                           reply_form=StaffReplyForm())


@bp.post("/reviews/<int:review_id>/toggle")
def review_toggle(review_id):
    r = db.session.get(ProductReview, review_id) or abort(404)
    r.is_hidden = not r.is_hidden
    audit("review.hide" if r.is_hidden else "review.show", "review", r.id, r.title)
    db.session.commit()
    flash("Review hidden from the storefront." if r.is_hidden else "Review is visible again.", "success")
    return redirect(url_for("seller.reviews"))


@bp.post("/reviews/<int:review_id>/reply")
def review_reply(review_id):
    r = db.session.get(ProductReview, review_id) or abort(404)
    form = StaffReplyForm()
    if form.validate_on_submit():
        r.staff_reply = form.reply.data or None
        db.session.commit()
        flash("Reply saved.", "success")
    return redirect(url_for("seller.reviews"))


# --------------------------------------------------- Open Food Facts import

@bp.route("/import")
def off_import():
    form = OFFSearchForm(request.args)
    results, count, error = [], 0, None
    searched = False
    page = max(1, request.args.get("page", 1, type=int))
    if request.args.get("q") and form.validate():
        searched = True
        try:
            results, count = off.search(form.q.data, page=page)
        except off.OFFUnavailable as exc:
            error = str(exc)
    imported = {p.off_barcode: p for p in Product.query.filter(Product.off_barcode.in_([r.barcode for r in results])).all()} if results else {}
    import_form = OFFImportForm()
    import_form.category_id.choices = [(c.id, c.name) for c in Category.query.order_by(Category.position)]
    tmpl = "seller/_off_results.html" if request.headers.get("X-Requested-With") == "fetch" else "seller/import.html"
    recent = Product.query.filter_by(source="openfoodfacts").order_by(Product.created_at.desc()).limit(6).all()
    return render_template(tmpl, form=form, results=results, count=count, error=error, searched=searched,
                           imported=imported, import_form=import_form, page=page, recent=recent)


@bp.post("/import")
def off_import_post():
    form = OFFImportForm()
    form.category_id.choices = [(c.id, c.name) for c in Category.query.order_by(Category.position)]
    back = url_for("seller.off_import", q=request.form.get("q", ""))
    if not form.validate_on_submit():
        for name, errs in form.errors.items():
            flash(f"{getattr(form, name).label.text or name}: {errs[0]}", "error")
            break
        return redirect(back)
    category = db.session.get(Category, form.category_id.data)
    try:
        product = off.import_product(form.barcode.data, category, form.price.minor, form.stock.data,
                                     PRODUCT_ACTIVE if form.publish.data else PRODUCT_DRAFT)
        db.session.flush()
        audit("off.import", "product", product.id, f"barcode {product.off_barcode}: {product.name}")
        db.session.commit()
    except off.OFFUnavailable as exc:
        flash(str(exc), "error")
        return redirect(back)
    except (ValueError, IntegrityError) as exc:
        db.session.rollback()
        flash(str(exc) if isinstance(exc, ValueError) else "This product was already imported.", "error")
        return redirect(back)
    flash(f"Imported {product.name} as {product.status}. Review it before publishing." if product.status == PRODUCT_DRAFT
          else f"Imported and published {product.name}.", "success")
    return redirect(url_for("seller.product_edit", product_id=product.id))


@bp.post("/products/<int:product_id>/resync")
def off_resync(product_id):
    product = db.session.get(Product, product_id) or abort(404)
    if not product.off_barcode:
        abort(400)
    try:
        data = off.get_product(product.off_barcode)
    except off.OFFUnavailable as exc:
        flash(str(exc), "error")
        return redirect(url_for("seller.product_edit", product_id=product.id))
    if data is None:
        flash("Open Food Facts no longer lists this barcode.", "error")
    else:
        product.ingredients = data.ingredients or product.ingredients
        product.allergens = data.allergens or product.allergens
        product.nutriscore = data.nutriscore or product.nutriscore
        product.nutrition_json = data.nutrition or product.nutrition_json
        product.off_categories = data.categories or product.off_categories
        product.synced_at = utcnow()
        audit("off.resync", "product", product.id, product.off_barcode)
        db.session.commit()
        flash("Refreshed ingredients and nutrition from Open Food Facts.", "success")
    return redirect(url_for("seller.product_edit", product_id=product.id))


# ----------------------------------------------------------------- exports

@bp.route("/export/<kind>.csv")
def export(kind):
    if kind == "products":
        body = reports.products_csv()
    elif kind == "orders":
        body = reports.orders_csv()
    else:
        abort(404)
    audit("export." + kind, None, None, "CSV export")
    db.session.commit()
    stamp = utcnow().strftime("%Y%m%d")
    return Response(body, mimetype="text/csv",
                    headers={"Content-Disposition": f"attachment; filename=aurelune-{kind}-{stamp}.csv"})


# ------------------------------------------------------------- model photos

@bp.route("/photos")
def photos():
    current = {slot: db.session.get(StoreSetting, setting_key(slot)) for slot in SLOTS}
    credits = {slot: (db.session.get(StoreSetting, credit_key(slot)) or StoreSetting(key="", value="")).value for slot in SLOTS}
    return render_template("seller/photos.html", slots=SLOTS, current=current, credits=credits,
                           pexels_ready=bool(pexels.api_key()))


@bp.post("/photos/<slot>")
def photo_upload(slot):
    if slot not in SLOTS:
        abort(404)
    try:
        name = save_product_image(request.files.get("photo"))
    except UploadError as exc:
        flash(str(exc), "error")
        return redirect(url_for("seller.photos"))
    row = db.session.get(StoreSetting, setting_key(slot))
    if row:
        delete_upload(row.value)
        row.value = name
    else:
        db.session.add(StoreSetting(key=setting_key(slot), value=name))
    own_credit = db.session.get(StoreSetting, credit_key(slot))
    if own_credit:
        db.session.delete(own_credit)  # your own photo has no Pexels credit
    audit("photo.update", "photo", slot, SLOTS[slot][0])
    db.session.commit()
    flash(f"{SLOTS[slot][0]} photo updated.", "success")
    return redirect(url_for("seller.photos"))


@bp.post("/photos/<slot>/reset")
def photo_reset(slot):
    if slot not in SLOTS:
        abort(404)
    row = db.session.get(StoreSetting, setting_key(slot))
    if row:
        delete_upload(row.value)
        db.session.delete(row)
        old_credit = db.session.get(StoreSetting, credit_key(slot))
        if old_credit:
            db.session.delete(old_credit)
        audit("photo.reset", "photo", slot, SLOTS[slot][0])
        db.session.commit()
    flash(f"{SLOTS[slot][0]} is back to the placeholder.", "info")
    return redirect(url_for("seller.photos"))


# ------------------------------------------------- Find photos (Pexels)

def _target(raw):
    """('slot', slot, label, query) or ('product', Product, name, query) from a ?target= value, else None."""
    kind, _, ident = (raw or "").partition(":")
    if kind == "slot" and ident in SLOTS:
        return "slot", ident, SLOTS[ident][0], SLOTS[ident][2]
    if kind == "product" and ident.isdigit():
        product = db.session.get(Product, int(ident))
        if product is not None:
            return "product", product, product.name, product_query(product)
    return None


@bp.route("/find-photos")
def find_photos():
    target = _target(request.args.get("target"))
    ready = bool(pexels.api_key())
    q = (request.args.get("q") or "").strip()[:100]
    page = max(1, request.args.get("page", 1, type=int))
    results, total, error = [], 0, None
    if target and ready:
        q = q or target[3]
        try:
            results, total = pexels.search(q, page)
        except pexels.PexelsError as exc:
            error = str(exc)
    products = Product.query.filter(Product.status != PRODUCT_ARCHIVED).order_by(Product.name).all()
    return render_template("seller/find_photos.html", target=target, target_raw=request.args.get("target", ""), q=q,
                           page=page, results=results, total=total, error=error, ready=ready, slots=SLOTS,
                           products=products, has_next=page * 18 < total,
                           suggestions=["fashion model portrait", "male model studio", "fashion editorial woman",
                                        "street style model", "wristwatch model", "jewelry model", "handbag model"])


@bp.post("/find-photos/use")
def find_photos_use():
    target = _target(request.form.get("target"))
    back = url_for("seller.find_photos", target=request.form.get("target", ""), q=request.form.get("q", ""),
                   page=request.form.get("page", 1, type=int))
    photo_id = request.form.get("photo_id", type=int)
    if target is None or not photo_id:
        abort(400)
    try:
        photo = pexels.get_photo(photo_id)  # re-fetched from Pexels by id: nothing from the browser is trusted
        filename = save_image_bytes(pexels.download(photo))
    except (pexels.PexelsError, UploadError) as exc:
        flash(str(exc), "error")
        return redirect(back)
    _apply_photo(target, filename, photo.credit)
    audit("photo.pexels", "photo", request.form.get("target"), f"{target[2]} ← Pexels #{photo.id} by {photo.photographer}")
    db.session.commit()
    flash(f"Photo added to {target[2]}. {photo.credit}.", "success")
    if target[0] == "product":
        return redirect(url_for("seller.product_edit", product_id=target[1].id))
    return redirect(url_for("seller.photos"))


@bp.post("/photos/autofill")
def photos_autofill():
    if not pexels.api_key():
        flash("Add your free Pexels key first, then auto-fill will work.", "info")
        return redirect(url_for("seller.find_photos"))
    todo = [slot for slot in SLOTS if db.session.get(StoreSetting, setting_key(slot)) is None]
    if not todo:
        flash("All five site photos are already set. Reset one to fill it again.", "info")
        return redirect(url_for("seller.photos"))
    used, filled = set(), 0
    try:
        for slot in todo:
            pick = _pick_photo(SLOTS[slot][2], used)
            if pick is None:
                continue
            _apply_photo(("slot", slot), save_image_bytes(pexels.download(pick)), pick.credit)
            used.add(pick.id)
            audit("photo.pexels", "photo", f"slot:{slot}", f"{SLOTS[slot][0]} ← Pexels #{pick.id} (auto-fill)")
            db.session.commit()
            filled += 1
    except (pexels.PexelsError, UploadError) as exc:
        db.session.rollback()
        flash(f"Stopped after {filled} photo(s): {exc}", "error")
        return redirect(url_for("seller.photos"))
    flash(f"Filled {filled} site photo(s) with professional model photos. Don't like one? Use “Find a photo” on its card.", "success")
    return redirect(url_for("seller.photos"))


@bp.post("/pexels-key")
def pexels_key():
    row = db.session.get(StoreSetting, "pexels_api_key")
    if request.form.get("action") == "remove":
        if row:
            db.session.delete(row)
            audit("pexels.key_removed", "settings", "pexels_api_key", "Pexels key removed")
            db.session.commit()
        flash("Pexels key removed.", "info")
        return redirect(request.referrer or url_for("seller.find_photos"))
    key = (request.form.get("key") or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9]{20,100}", key):
        flash("That doesn't look like a Pexels key. It's one long line of letters and numbers.", "error")
        return redirect(request.referrer or url_for("seller.find_photos"))
    try:
        pexels.search("fashion model", per_page=1, key=key)  # prove the key works BEFORE storing it
    except pexels.PexelsError as exc:
        flash(str(exc), "error")
        return redirect(request.referrer or url_for("seller.find_photos"))
    if row:
        row.value = key
    else:
        db.session.add(StoreSetting(key="pexels_api_key", value=key))
    audit("pexels.key_saved", "settings", "pexels_api_key", "Pexels key saved")
    db.session.commit()
    flash("Pexels key saved. You can search for photos now.", "success")
    return redirect(request.referrer or url_for("seller.find_photos"))


@bp.post("/products/autofill-photos")
def products_autofill_photos():
    """Give every product with a missing or broken photo a right-looking one from the internet."""
    try:
        result = photo_fill.fill_products(limit=30)
    except pexels.PexelsError as exc:
        flash(str(exc), "error")
        return redirect(url_for("seller.products"))
    if not result.needed:
        flash("Every product already has a photo that loads. Nothing to fill in.", "success")
        return redirect(url_for("seller.products"))
    if result.error:
        flash(f"Stopped after {len(result.done)} product(s): {result.error}", "error")
        return redirect(url_for("seller.products"))
    msg = f"Added photos to {len(result.done)} product(s) (from {result.source})."
    if result.left:
        msg += f" {result.left} more are left. Press the button again."
    if result.skipped:
        msg += f" No photo found for: {', '.join(result.skipped)}."
    flash(msg + " Look them over, and use “Find a model photo” on any you want to swap.", "success")
    return redirect(url_for("seller.products"))
