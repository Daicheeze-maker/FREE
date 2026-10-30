"""Administrator console: users, roles, settings, API health, audit log, reports."""
from datetime import timedelta

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user
from sqlalchemy import or_

from ..extensions import db
from ..forms import SettingsForm, UserAdminForm
from ..models import (ROLE_ADMIN, ROLES, ApiStatus, AuditLog, ExchangeRateCache, NewsletterSubscription, Order,
                      StoreSetting, User, get_int_setting, get_setting, utcnow)
from ..money import to_major
from ..security import audit, roles_required
from ..services import api_health, currency, reports
from ..services import openfoodfacts as off

bp = Blueprint("admin", __name__, url_prefix="/admin")


@bp.before_request
@roles_required("admin")
def _guard():
    return None


@bp.route("/")
def dashboard():
    series = reports.chart_series(reports.daily_revenue(30))
    role_counts = dict(db.session.query(User.role, db.func.count(User.id)).group_by(User.role).all())
    apis = {a.name: a for a in ApiStatus.query.all()}
    return render_template("admin/dashboard.html", k=reports.kpis(), series=series,
                           breakdown=reports.status_breakdown(), role_counts=role_counts,
                           audit=AuditLog.query.order_by(AuditLog.created_at.desc()).limit(8).all(),
                           apis=apis, by_cat=reports.inventory_by_category(),
                           disabled=User.query.filter_by(is_active_account=False).count(),
                           locked=User.query.filter(User.locked_until > utcnow()).count(),
                           subscribers=NewsletterSubscription.query.count(),
                           recent_orders=Order.query.order_by(Order.created_at.desc()).limit(6).all())


@bp.route("/users")
def users():
    q = request.args.get("q", "").strip()[:100]
    role = request.args.get("role", "")
    state = request.args.get("state", "")
    query = User.query
    if q:
        query = query.filter(or_(User.email.ilike(f"%{q}%"), User.full_name.ilike(f"%{q}%")))
    if role in ROLES:
        query = query.filter_by(role=role)
    if state == "disabled":
        query = query.filter_by(is_active_account=False)
    elif state == "locked":
        query = query.filter(User.locked_until > utcnow())
    page = request.args.get("page", 1, type=int)
    pagination = query.order_by(User.created_at.desc()).paginate(page=max(page, 1), per_page=25, error_out=False)
    order_counts = dict(db.session.query(Order.user_id, db.func.count(Order.id)).group_by(Order.user_id).all())
    return render_template("admin/users.html", pagination=pagination, q=q, role=role, state=state, roles=ROLES,
                           order_counts=order_counts, now=utcnow())


@bp.route("/users/<int:user_id>", methods=["GET", "POST"])
def user_detail(user_id):
    user = db.session.get(User, user_id) or abort(404)
    form = UserAdminForm(obj=user)
    if form.validate_on_submit():
        new_role, new_active = form.role.data, form.is_active_account.data
        if user.id == current_user.id and (new_role != ROLE_ADMIN or not new_active):
            flash("You can't remove your own admin access or disable your own account.", "error")
            return redirect(url_for("admin.user_detail", user_id=user.id))
        if user.role == ROLE_ADMIN and (new_role != ROLE_ADMIN or not new_active):
            active_admins = User.query.filter_by(role=ROLE_ADMIN, is_active_account=True).count()
            if active_admins <= 1:
                flash("At least one active administrator is required.", "error")
                return redirect(url_for("admin.user_detail", user_id=user.id))
        if new_role != user.role:
            audit("user.role_change", "user", user.id, f"{user.email}: {user.role} → {new_role}")
            user.role = new_role
        if new_active != user.is_active_account:
            audit("user.disable" if not new_active else "user.enable", "user", user.id, user.email)
            user.is_active_account = new_active
        db.session.commit()
        flash("User updated.", "success")
        return redirect(url_for("admin.user_detail", user_id=user.id))
    orders = Order.query.filter_by(user_id=user.id).order_by(Order.created_at.desc()).limit(10).all()
    logs = AuditLog.query.filter(or_(AuditLog.actor_id == user.id,
                                     (AuditLog.target_type == "user") & (AuditLog.target_id == str(user.id))))\
        .order_by(AuditLog.created_at.desc()).limit(15).all()
    return render_template("admin/user_detail.html", user=user, form=form, orders=orders, logs=logs, now=utcnow())


@bp.post("/users/<int:user_id>/unlock")
def user_unlock(user_id):
    user = db.session.get(User, user_id) or abort(404)
    user.locked_until, user.failed_login_count = None, 0
    audit("user.unlock", "user", user.id, user.email)
    db.session.commit()
    flash("Login lock cleared.", "success")
    return redirect(url_for("admin.user_detail", user_id=user.id))


@bp.route("/reports")
def reports_view():
    days = request.args.get("days", 30, type=int)
    days = days if days in (7, 30, 90) else 30
    series = reports.chart_series(reports.daily_revenue(days))
    since = utcnow() - timedelta(days=days)
    return render_template("admin/reports.html", series=series, days=days,
                           revenue=reports.revenue_minor(since), orders=reports.order_count(since, reports.COUNTED),
                           top=reports.top_products(10), by_cat=reports.inventory_by_category(),
                           breakdown=reports.status_breakdown(), low=reports.low_stock())


@bp.route("/settings", methods=["GET", "POST"])
def settings():
    form = SettingsForm()
    if request.method == "GET":
        form.shipping_flat.data = str(to_major(get_int_setting("shipping_flat_minor")))
        form.free_shipping_threshold.data = str(to_major(get_int_setting("free_shipping_threshold_minor")))
        form.low_stock_threshold.data = get_int_setting("low_stock_threshold")
        form.store_announcement.data = get_setting("store_announcement")
        form.support_email.data = get_setting("support_email")
    if form.validate_on_submit():
        values = {
            "shipping_flat_minor": str(form.shipping_flat.minor),
            "free_shipping_threshold_minor": str(form.free_shipping_threshold.minor),
            "low_stock_threshold": str(form.low_stock_threshold.data),
            "store_announcement": form.store_announcement.data or "",
            "support_email": form.support_email.data,
        }
        changed = []
        for key, value in values.items():
            row = db.session.get(StoreSetting, key)
            if row is None:
                db.session.add(StoreSetting(key=key, value=value))
                changed.append(key)
            elif row.value != value:
                row.value = value
                changed.append(key)
        if changed:
            audit("settings.update", "settings", None, ", ".join(changed))
        db.session.commit()
        flash("Store settings saved.", "success")
        return redirect(url_for("admin.settings"))
    return render_template("admin/settings.html", form=form)


@bp.route("/api-health")
def api_health_view():
    apis = {a.name: a for a in ApiStatus.query.all()}
    rates = ExchangeRateCache.query.order_by(ExchangeRateCache.target).all()
    return render_template("admin/api_health.html", apis=apis, rates=rates, now=utcnow(),
                           OFF=api_health.OFF, FX=api_health.FRANKFURTER)


@bp.post("/api-health/<name>/test")
def api_test(name):
    if name == api_health.FRANKFURTER:
        try:
            n = currency.refresh_cache(force=True)
            flash(f"Frankfurter OK — refreshed {n} exchange rates.", "success")
        except currency.RatesUnavailable as exc:
            flash(f"Frankfurter unavailable: {exc}", "error")
    elif name == api_health.OFF:
        try:
            results, count = off.search("oat", page_size=3)
            flash(f"Open Food Facts OK — search returned {count:,} matches.", "success")
        except off.OFFUnavailable as exc:
            flash(f"Open Food Facts unavailable: {exc}", "error")
    else:
        abort(404)
    audit("api.test", "api", name, "Manual connectivity test", commit=True)
    return redirect(url_for("admin.api_health_view"))


@bp.route("/audit")
def audit_log():
    action = request.args.get("action", "").strip()[:60]
    query = AuditLog.query
    if action:
        query = query.filter(AuditLog.action.ilike(f"{action}%"))
    page = request.args.get("page", 1, type=int)
    pagination = query.order_by(AuditLog.created_at.desc()).paginate(page=max(page, 1), per_page=40, error_out=False)
    actions = [a[0] for a in db.session.query(AuditLog.action).distinct().order_by(AuditLog.action).all()]
    return render_template("admin/audit.html", pagination=pagination, action=action, actions=actions)
