import time
from collections import defaultdict, deque
from datetime import timedelta
from threading import Lock

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required, login_user, logout_user

from ..extensions import db
from ..forms import LoginForm, RegisterForm
from ..models import ROLE_CUSTOMER, User, utcnow
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


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(home_for(current_user))
    form = LoginForm()
    if form.validate_on_submit():
        if _ip_throttled():
            abort(429)
        user = User.query.filter_by(email=form.email.data.lower()).first()
        now = utcnow()
        if user and user.locked_until and user.locked_until > now:
            mins = max(1, int((user.locked_until - now).total_seconds() // 60) + 1)
            flash(f"Too many failed attempts. Try again in about {mins} minute(s).", "error")
        elif user and user.check_password(form.password.data):
            if not user.is_active_account:
                flash("This account has been disabled. Contact support if you think this is a mistake.", "error")
                return render_template("auth/login.html", form=form), 403
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
            flash(f"Welcome back, {user.first_name}.", "success")
            nxt = request.args.get("next")
            return redirect(nxt if is_safe_redirect(nxt) else home_for(user))
        else:
            if user:
                user.failed_login_count += 1
                if user.failed_login_count >= current_app.config["LOGIN_MAX_ATTEMPTS"]:
                    user.locked_until = now + timedelta(minutes=current_app.config["LOGIN_LOCK_MINUTES"])
                    user.failed_login_count = 0
                    audit("auth.lockout", "user", user.id, "Account temporarily locked after failed logins", actor=user)
                db.session.commit()
            flash("That email and password don't match.", "error")
    return render_template("auth/login.html", form=form)


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
            notify(user.id, "Welcome to Velora Market", "Use WELCOME10 for 10% off your first order.",
                   url_for("catalog.listing"), icon="sparkles")
            db.session.commit()
            flash("Your account is ready. Welcome to Velora!", "success")
            nxt = request.args.get("next")
            return redirect(nxt if is_safe_redirect(nxt) else url_for("account.dashboard"))
    return render_template("auth/register.html", form=form)


@bp.post("/logout")
@login_required
def logout():
    logout_user()
    session.clear()
    flash("You've been signed out.", "info")
    return redirect(url_for("main.home"))
