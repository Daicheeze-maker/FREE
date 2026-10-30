"""Velora Market — application factory."""
import logging
import os
import secrets

from pathlib import Path

from dotenv import load_dotenv

# Load .env before config is imported: Config reads os.environ at class-definition time.
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from flask import Flask, g, jsonify, render_template, request  # noqa: E402
from flask_login import current_user  # noqa: E402
from flask_wtf.csrf import CSRFError  # noqa: E402

from .config import BASE_DIR, CONFIGS  # noqa: E402
from .extensions import csrf, db, login_manager, migrate  # noqa: E402


def create_app(config_name=None, **overrides):
    config_name = config_name or os.environ.get("VELORA_ENV", "development")
    app = Flask(__name__, instance_path=str(BASE_DIR / "instance"))
    app.config.from_object(CONFIGS.get(config_name, CONFIGS["development"]))
    app.config.update(overrides)

    if not app.config.get("SECRET_KEY"):
        if config_name == "production":
            raise RuntimeError("SECRET_KEY must be set in production (see .env.example).")
        # Dev convenience: a random key per process (sessions reset on restart).
        app.config["SECRET_KEY"] = secrets.token_hex(32)
        app.logger.warning("SECRET_KEY not set — using a temporary random key. Set it in .env.")

    for key in ("DATA_DIR", "UPLOAD_FOLDER"):
        os.makedirs(app.config[key], exist_ok=True)

    db.init_app(app)
    migrate.init_app(app, db, directory=str(BASE_DIR / "migrations"))
    csrf.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Please sign in to continue."
    login_manager.login_message_category = "info"
    login_manager.session_protection = "strong"

    from .models import User

    @login_manager.user_loader
    def load_user(user_id):
        try:
            return db.session.get(User, int(user_id))
        except (TypeError, ValueError):
            return None

    from .blueprints import account, admin, auth, catalog, main, seller, shop
    for bp in (main.bp, catalog.bp, auth.bp, shop.bp, account.bp, seller.bp, admin.bp):
        app.register_blueprint(bp)

    _register_template_helpers(app)
    _register_error_handlers(app)

    from .security import apply_security_headers
    app.after_request(apply_security_headers)

    from .cli import register_cli
    register_cli(app)

    if not app.debug and not app.testing:
        logging.basicConfig(level=logging.INFO)
    return app


def _register_template_helpers(app):
    from .models import Category, WishlistItem, get_int_setting, get_setting
    from .money import fmt_minor
    from .services import cart as cart_service
    from .services.currency import PriceDisplay

    @app.context_processor
    def inject_globals():
        if request.endpoint == "main.health":
            return {}
        if "money" not in g:
            g.money = PriceDisplay()
        wish_ids = set()
        if current_user.is_authenticated:
            wish_ids = {w.product_id for w in WishlistItem.query.filter_by(user_id=current_user.id)}
        return {
            "money": g.money,
            "fmt_base": fmt_minor,
            "cart_count": cart_service.count(),
            "nav_categories": Category.query.order_by(Category.position, Category.name).all(),
            "announcement": get_setting("store_announcement"),
            "support_email": get_setting("support_email"),
            "free_ship_minor": get_int_setting("free_shipping_threshold_minor"),
            "currencies": app.config["DISPLAY_CURRENCIES"],
            "wishlist_ids": wish_ids,
        }

    @app.template_filter("dt")
    def format_dt(value, fmt="%b %d, %Y"):
        return value.strftime(fmt) if value else "—"

    @app.template_filter("dtt")
    def format_dtt(value):
        return value.strftime("%b %d, %Y · %H:%M UTC") if value else "—"

    @app.template_filter("reject_page")
    def reject_page(args):
        return {k: v for k, v in args.items() if k != "page"}

    @app.template_global()
    def site_photo(slot):
        """Uploaded model photo for a site slot, or the default stock image."""
        from flask import url_for
        from .photos import SLOTS, setting_key
        filename = get_setting(setting_key(slot))
        if filename:
            return url_for("main.media", filename=filename)
        return SLOTS[slot][2]

    @app.template_global()
    def image_src(img):
        from flask import url_for
        if img is None:
            return url_for("static", filename="img/placeholder.svg")
        if img.filename:
            return url_for("main.media", filename=img.filename)
        return img.url or url_for("static", filename="img/placeholder.svg")


def _register_error_handlers(app):
    def wants_json():
        return request.accept_mimetypes.best == "application/json" or request.headers.get("X-Requested-With") == "fetch"

    def render_error(code, title, message):
        if wants_json():
            return jsonify(ok=False, error=message), code
        return render_template("errors/error.html", code=code, title=title, message=message), code

    @app.errorhandler(400)
    def bad_request(e):
        return render_error(400, "Bad request", "Something about that request wasn't right.")

    @app.errorhandler(CSRFError)
    def csrf_error(e):
        return render_error(400, "Session expired", "Your form expired for security reasons. Please go back, refresh and try again.")

    @app.errorhandler(403)
    def forbidden(e):
        return render_error(403, "Not allowed", "You don't have permission to view this page.")

    @app.errorhandler(404)
    def not_found(e):
        return render_error(404, "Page not found", "We couldn't find what you were looking for.")

    @app.errorhandler(413)
    def too_large(e):
        return render_error(413, "File too large", "That upload is larger than the allowed size.")

    @app.errorhandler(429)
    def too_many(e):
        return render_error(429, "Slow down", "Too many attempts. Please wait a few minutes.")

    @app.errorhandler(500)
    def server_error(e):
        db.session.rollback()
        return render_error(500, "Something went wrong", "An unexpected error occurred. Our team has been notified.")
