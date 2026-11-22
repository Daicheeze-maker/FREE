import secrets
from urllib.parse import urlparse
import time
from collections import defaultdict, deque
from datetime import timedelta
from threading import Lock

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required, login_user, logout_user

from ..extensions import db
from ..forms import AdminSetupForm, LoginForm, RegisterForm
from ..models import ROLE_CUSTOMER, ROLE_SELLER, SELLER_SUFFIX, User, utcnow
from ..security import audit, client_ip, is_safe_redirect
from ..services import cart as cart_service

bp = Blueprint("auth", __name__, url_prefix="/account")

# Per-IP throttle (in-process, per app). Per-account lockout below is persisted in the
# database, so it also holds across multiple Gunicorn workers.
_ip_lock = Lock()
IP_WINDOW_SECONDS, IP_MAX_ATTEMPTS = 300, 20


def _ip_throttled():
    now = time.monotonic()
    attempts = current_app.extensions.setdefault("velora_login_attempts", defaultdict(deque))
    with _ip_lock:
        q = attempts[client_ip()]
        while q and now - q[0] > IP_WINDOW_SECONDS:
            q.popleft()
        if len(q) >= IP_MAX_ATTEMPTS:
            return True
        q.append(now)
    return False


def home_for(user):
    if user.role == "admin":
        return url_for("admin.dashboard")
    if user.role == "seller":
        return url_for("seller.dashboard")
    return url_for("account.dashboard")


def _page_exists(path, user):
    """Does this address lead to a real page for this user? (a stale ?next= must not end on a 404)"""
    from ..models import Category, Order, Product
    try:
        endpoint, args = current_app.url_map.bind("localhost").match(path.split("?")[0], method="GET")
    except Exception:
        return False
    if endpoint == "catalog.listing" and args.get("slug"):
        return Category.query.filter_by(slug=args["slug"]).first() is not None
    if endpoint == "catalog.detail":
        return Product.query.filter_by(slug=args["slug"]).first() is not None
    if endpoint == "account.order_detail":
        return Order.query.filter_by(number=args["number"], user_id=user.id).first() is not None
    return True



@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(home_for(current_user))
    form = LoginForm()
    if form.validate_on_submit():
        if _ip_throttled():
            abort(429)
        email = form.email.data.lower().removesuffix(SELLER_SUFFIX)
        user = User.query.filter_by(email=email).first()  # accounts are only created on the Create account page
        now = utcnow()
        is_buyer = user is not None and user.role == ROLE_CUSTOMER
        if user and user.locked_until and user.locked_until > now:
            mins = max(1, int((user.locked_until - now).total_seconds() // 60) + 1)
            flash(f"Too many failed attempts. Try again in about {mins} minute(s).", "error")
        elif user and user.check_password(form.password.data):
            if not user.is_active_account:
                flash("This account has been disabled. Contact support if you think this is a mistake.", "error")
                return render_template("auth/login.html", form=form, admin_setup=admin_setup_open()), 403
            user.failed_login_count = 0
            user.locked_until = None
            user.last_login_at = now
            db.session.commit()
            guest_currency = session.get("currency")
            recent = session.get("recently_viewed")
            guest_cart = session.get(cart_service.SESSION_KEY)
            session.clear()  # rotate session on privilege change
            if guest_cart:
                session[cart_service.SESSION_KEY] = guest_cart
            if guest_currency:
                session["currency"] = guest_currency
            if recent:
                session["recently_viewed"] = recent
            login_user(user, remember=form.remember.data)
            cart_service.merge_session_cart_into(user)
            if request.args.get("as") == "seller" and user.role == ROLE_CUSTOMER:
                # "Sign in as the seller profile": the same person's linked seller profile
                seller = user.linked_profile
                if seller is not None and seller.is_active_account:
                    logout_user()
                    login_user(seller, remember=form.remember.data)
                    flash(f"Welcome back, {seller.first_name}. You're using your seller profile.", "success")
                    return redirect(home_for(seller))
            flash(f"Welcome back, {user.first_name}.", "success")
            nxt = request.args.get("next")
            return redirect(nxt if is_safe_redirect(nxt) and _page_exists(urlparse(nxt).path, user) else home_for(user))
        else:
            if user:
                user.failed_login_count += 1
                if user.failed_login_count >= current_app.config["LOGIN_MAX_ATTEMPTS"]:
                    user.locked_until = now + timedelta(minutes=current_app.config["LOGIN_LOCK_MINUTES"])
                    user.failed_login_count = 0
                    audit("auth.lockout", "user", user.id, "Account temporarily locked after failed logins", actor=user)
                db.session.commit()
            flash("That email and password don't match.", "error")
    return render_template("auth/login.html", form=form, admin_setup=admin_setup_open())


@bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(home_for(current_user))
    form = RegisterForm()
    if form.validate_on_submit():
        email = form.email.data.lower()
        if User.query.filter_by(email=email).first():
            form.email.errors.append("An account with this email already exists.")
        else:
            user = User(email=email, full_name=form.full_name.data, role=ROLE_CUSTOMER)
            user.set_password(form.password.data)
            db.session.add(user)
            db.session.commit()
            guest_cart = session.get(cart_service.SESSION_KEY)
            login_user(user)
            if guest_cart:
                session[cart_service.SESSION_KEY] = guest_cart
                cart_service.merge_session_cart_into(user)
            from ..services.orders import notify
            notify(user.id, f"Welcome to {current_app.config['BRAND_NAME']}", "Use WELCOME10 for 10% off your first order.",
                   url_for("catalog.listing"), icon="sparkles")
            db.session.commit()
            if (form.account_type.data or "buyer") == "seller":
                # Selling needs the admin's approval: take them straight to the application
                flash("Your account is ready. Now tell us about your shop: an admin reviews every seller application.", "success")
                return redirect(url_for("account.seller_application"))
            flash(f"Your account is ready. Welcome to {current_app.config['BRAND_NAME']}!", "success")
            nxt = request.args.get("next")
            return redirect(nxt if is_safe_redirect(nxt) else url_for("account.dashboard"))
    return render_template("auth/register.html", form=form)


def admin_setup_open():
    """The one-time admin set-up page works only while the store has no admin, and only from this computer itself."""
    from ..models import ROLE_ADMIN
    local = (request.remote_addr or "") in ("127.0.0.1", "::1") and not request.headers.get("X-Forwarded-For")
    return local and User.query.filter_by(role=ROLE_ADMIN).first() is None


@bp.route("/setup-admin", methods=["GET", "POST"])
def setup_admin():
    from ..models import ROLE_ADMIN
    if not admin_setup_open():
        abort(404)
    form = AdminSetupForm()
    if form.validate_on_submit():
        email = form.email.data.lower()
        user = User.query.filter_by(email=email).first()
        if user is None:
            user = User(email=email, full_name=form.full_name.data, role=ROLE_ADMIN)
            db.session.add(user)
        else:  # an email already used for a shop account becomes the admin
            user.role, user.full_name = ROLE_ADMIN, form.full_name.data
            linked = User.query.filter_by(email=email + SELLER_SUFFIX).first()
            if linked is not None:
                linked.is_active_account = False
        user.set_password(form.password.data)
        user.is_active_account, user.failed_login_count, user.locked_until = True, 0, None
        db.session.flush()
        audit("admin.setup", "user", user.id, f"First admin account set up: {email}", actor=user)
        db.session.commit()
        logout_user()
        session.clear()
        login_user(user)
        flash("Your admin account is ready. Welcome to the Admin console!", "success")
        return redirect(url_for("admin.dashboard"))
    return render_template("auth/setup_admin.html", form=form)


@bp.post("/switch-profile")
@login_required
def switch_profile():
    other = current_user.linked_profile
    if other is None or not other.is_active_account:
        abort(404)
    logout_user()
    login_user(other)
    other.last_login_at = utcnow()
    db.session.commit()
    flash(f"You're now using your {'seller' if other.role == ROLE_SELLER else 'buyer'} profile.", "success")
    return redirect(home_for(other))


@bp.post("/logout")
@login_required
def logout():
    logout_user()
    session.clear()
    flash("You've been signed out.", "info")
    return redirect(url_for("main.home"))
