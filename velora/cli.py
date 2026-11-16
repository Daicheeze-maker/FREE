"""Flask CLI commands: `flask --app wsgi <command>`."""
import click
import requests
from flask import current_app
from sqlalchemy import inspect

from .extensions import db


def init_database():
    """Create or upgrade the schema via migrations. Never drops data."""
    from flask_migrate import upgrade
    upgrade(directory=current_app.extensions["migrate"].directory)


DEMO_ADMIN = "admin@velora.example"
DEMO_BUYERS = ("buyer1@velora.example", "buyer2@velora.example")


def demo_status():
    """Is the data in this database the CURRENT demo catalog?

    'empty'    - nothing loaded yet (seed will load it)
    'current'  - the up-to-date demo catalog
    'stale'    - the demo catalog from a slightly older release (e.g. no Shoes/Accessories yet): refreshed
                 automatically WITHOUT deleting anything
    'outdated' - a much older version of the demo store (still has Cars): replaced only if you say yes
    'custom'   - somebody's own store (none of the demo products): never touched automatically
    """
    from .models import Category, Product
    from .seed import KNOWN_MOVES
    if Category.query.first() is None:
        return "empty"
    if Product.query.filter_by(slug="linen-wrap-midi-dress").first() is None:
        return "custom"
    has_cars = Category.query.filter_by(slug="cars").first() is not None
    has_bags = Category.query.filter_by(slug="bags").first() is not None
    if has_cars or not has_bags:
        return "outdated"
    wanted = {"shoes", "accessories"}
    have = {c.slug for c in Category.query.filter(Category.slug.in_(wanted))}
    moved = all(
        (p := Product.query.filter_by(slug=slug).first()) is None or p.category.slug == target
        for slug, target in KNOWN_MOVES.items())
    return "current" if (have == wanted and moved) else "stale"


def remove_demo_accounts():
    """Delete the sample accounts older versions created (buyer1/buyer2/admin @velora.example + their seller
    profiles) together with their sample orders, reviews, addresses, wishlists and notifications.

    An account is kept (and reported) if it has any order that is not a seeded sample order.
    Returns (removed_emails, kept_emails).
    """
    from .models import (SELLER_SUFFIX, Address, Cart, CartItem, Notification, Order, ProductReview, User,
                         WishlistItem)
    emails = [DEMO_ADMIN, *DEMO_BUYERS]
    emails += [e + SELLER_SUFFIX for e in DEMO_BUYERS]
    removed, kept = [], []
    for user in User.query.filter(User.email.in_(emails)).all():
        orders = Order.query.filter_by(user_id=user.id).all()
        if any(not (o.checkout_token or "").startswith("seed-") for o in orders):
            kept.append(user.email)
            continue
        for o in orders:
            db.session.delete(o)
        ProductReview.query.filter_by(user_id=user.id).delete()
        WishlistItem.query.filter_by(user_id=user.id).delete()
        Notification.query.filter_by(user_id=user.id).delete()
        Address.query.filter_by(user_id=user.id).delete()
        for cart in Cart.query.filter_by(user_id=user.id).all():
            CartItem.query.filter_by(cart_id=cart.id).delete()
            db.session.delete(cart)
        db.session.delete(user)
        removed.append(user.email)
    db.session.commit()
    return removed, kept


def wipe_and_reseed():
    """Drop every table and load the current demo store. DESTROYS all data in the database."""
    from .seed import seed
    db.session.remove()
    db.drop_all()
    db.session.execute(db.text("DROP TABLE IF EXISTS alembic_version"))
    db.session.commit()
    init_database()
    seed()


def register_cli(app):
    @app.cli.command("init-db")
    def init_db_cmd():
        """Create/upgrade the database schema (non-destructive)."""
        init_database()
        tables = inspect(db.engine).get_table_names()
        click.echo(f"Database ready at {current_app.config['SQLALCHEMY_DATABASE_URI']} ({len(tables)} tables).")

    @app.cli.command("seed")
    def seed_cmd():
        """Load demo data into an EMPTY database (no-op if users already exist)."""
        from .seed import seed
        init_database()
        if seed():
            click.echo("Loaded the store catalog. Create your own account on the site (Create account).")
        else:
            click.echo("Catalog already has data — seed skipped (nothing was changed).")

    @app.cli.command("reset-demo")
    @click.option("--yes-delete-everything", is_flag=True, help="Required confirmation flag.")
    def reset_cmd(yes_delete_everything):
        """DANGER: drop all tables and re-seed. Refuses to run in production."""
        if current_app.config.get("ENV_NAME") == "production":
            raise click.ClickException("reset-demo is disabled when VELORA_ENV=production.")
        if not yes_delete_everything:
            raise click.ClickException("Pass --yes-delete-everything to confirm deleting ALL data.")
        wipe_and_reseed()
        click.echo("Demo database reset and re-seeded.")

    @app.cli.command("upgrade-demo")
    @click.option("--yes", is_flag=True, help="Update without asking.")
    def upgrade_demo_cmd(yes):
        """If the demo store is an older version, offer to replace it with the current one."""
        import sys
        init_database()
        removed, kept = remove_demo_accounts()
        if removed:
            click.echo(f" Removed {len(removed)} old sample account(s): {', '.join(removed)}")
        if kept:
            click.echo(f" Kept sample account(s) that have real orders: {', '.join(kept)}")
        status = demo_status()
        if status == "stale":
            from .seed import refresh_catalog
            for change in refresh_catalog():  # safe: adds/moves things, deletes no accounts, orders or photos
                click.echo(f" Catalog updated: {change}")
            return
        if status != "outdated":
            return  # up to date, empty, or someone's own store: nothing to do (and nothing printed)
        if current_app.config.get("ENV_NAME") == "production":
            click.echo("Demo data is outdated, but it is never replaced automatically in production.")
            return
        click.echo("")
        click.echo("=" * 70)
        click.echo(" Your store data is from an OLDER VERSION of Aurelune")
        click.echo(" (it still has Cars and the old catalog).")
        click.echo(" Updating loads the new catalog: Bags, Shoes, Accessories, sizes and the map.")
        click.echo(" It REPLACES everything in the local database (accounts, orders, uploads' links).")
        click.echo("=" * 70)
        if not yes:
            if not sys.stdin.isatty():
                click.echo(" Run this in a terminal to update:  python -m flask --app wsgi upgrade-demo")
                return
            if not click.confirm(" Update to the new demo store now?", default=False):
                click.echo(" OK, keeping your current data (you will still see the old catalog).")
                return
        wipe_and_reseed()
        click.echo(" Done: the new demo store is loaded.")
        click.echo("")

    @app.cli.command("create-admin")
    @click.option("--email", prompt=True)
    @click.option("--name", prompt="Full name")
    @click.password_option()
    def create_admin(email, name, password):
        """Create an administrator account."""
        from .models import User
        if User.query.filter_by(email=email.lower()).first():
            raise click.ClickException("A user with that email already exists.")
        u = User(email=email.lower(), full_name=name, role="admin")
        u.set_password(password)
        db.session.add(u)
        db.session.commit()
        click.echo(f"Administrator {email} created.")

    @app.cli.command("refresh-rates")
    def refresh_rates():
        """Fetch latest exchange rates from Frankfurter into the cache."""
        from .services.currency import RatesUnavailable, refresh_cache
        try:
            click.echo(f"Stored {refresh_cache(force=True)} rates.")
        except RatesUnavailable as exc:
            raise click.ClickException(f"Frankfurter unavailable: {exc}")

    @app.cli.command("load-model-photos")
    @click.option("--folder", default=None, help="Defaults to the project's model-photos/ folder.")
    def load_model_photos_cmd(folder):
        """Use your own model photos for the site slots and products (see model-photos/README.txt)."""
        from .config import BASE_DIR
        report = load_model_photos(folder or BASE_DIR / "model-photos")
        click.echo(f"Updated {report['slots']} site photo(s) and {report['products']} product(s).")
        for line in report["skipped"]:
            click.echo(f"  skipped {line}")

    @app.cli.command("fill-photos")
    @click.option("--limit", default=30, show_default=True)
    def fill_photos_cmd(limit):
        """Give products with a missing or broken photo a matching one from the internet (never fails the start-up)."""
        from .services import photo_fill, pexels
        try:
            res = photo_fill.fill_products(limit=limit)
        except pexels.PexelsError:
            click.echo(" Product photos: no internet right now, so none were added. They are filled in next time.")
            return
        except Exception as exc:  # start-up must never break because of photos
            click.echo(f" Product photos skipped ({type(exc).__name__}).")
            return
        if res.done:
            click.echo(f" Added photos to {len(res.done)} product(s) from {res.source}.")
        if res.error:
            click.echo(f" Stopped early: {res.error}")
        if res.left:
            click.echo(f" {res.left} more product(s) still need photos; they are filled in on the next start.")

    @app.cli.command("check-images")
    def check_images():
        """Verify that every remote product image URL actually loads."""
        from .models import ProductImage
        from .services.api_health import user_agent
        bad = 0
        for img in ProductImage.query.filter(ProductImage.url.isnot(None)).all():
            try:
                r = requests.get(img.url, headers={"User-Agent": user_agent()}, timeout=10, stream=True)
                ok = r.ok and r.headers.get("Content-Type", "").startswith("image/")
                r.close()
            except requests.RequestException as exc:
                ok, r = False, exc
            if not ok:
                bad += 1
                click.echo(f"BROKEN  product #{img.product_id}  {img.url}")
        click.echo("All remote images load." if not bad else f"{bad} broken image(s) — they fall back to a placeholder.")


def load_model_photos(folder):
    """Attach photos from FOLDER: <slot>.<ext> for site slots, products/<product-slug>/*.<ext> for products."""
    from pathlib import Path

    from werkzeug.datastructures import FileStorage

    from .models import Product, ProductImage, StoreSetting
    from .photos import SLOTS, setting_key
    from .services.uploads import UploadError, delete_upload, save_product_image

    folder = Path(folder)
    exts = {".jpg", ".jpeg", ".png", ".webp"}
    report = {"slots": 0, "products": 0, "skipped": []}

    def store(path):
        with open(path, "rb") as fh:
            return save_product_image(FileStorage(stream=fh, filename=path.name))

    for path in sorted(folder.glob("*")):
        if path.suffix.lower() in exts and path.stem.lower() in SLOTS:
            try:
                name = store(path)
            except UploadError as exc:
                report["skipped"].append(f"{path.name}: {exc}")
                continue
            row = db.session.get(StoreSetting, setting_key(path.stem.lower()))
            if row:
                delete_upload(row.value)
                row.value = name
            else:
                db.session.add(StoreSetting(key=setting_key(path.stem.lower()), value=name))
            report["slots"] += 1

    for pdir in sorted((folder / "products").glob("*")) if (folder / "products").is_dir() else []:
        if not pdir.is_dir():
            continue
        product = Product.query.filter_by(slug=pdir.name).first()
        if product is None:
            report["skipped"].append(f"products/{pdir.name}: no product with that slug")
            continue
        files = sorted(p for p in pdir.iterdir() if p.suffix.lower() in exts)
        new = []
        for path in files:
            try:
                new.append(ProductImage(filename=store(path), alt=f"{product.name} — modelled by our team"))
            except UploadError as exc:
                report["skipped"].append(f"products/{pdir.name}/{path.name}: {exc}")
        if new:
            ordered = new + list(product.images)  # your photos go first, so the first becomes the cover
            for img in new:
                product.images.append(img)
            for pos, img in enumerate(ordered):
                img.position = pos
            report["products"] += 1
    db.session.commit()
    return report
