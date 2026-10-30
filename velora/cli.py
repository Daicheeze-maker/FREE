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
            click.echo("Seeded demo data. Sign in with the demo accounts listed in README.md.")
        else:
            click.echo("Database already has data — seed skipped (nothing was changed).")

    @app.cli.command("reset-demo")
    @click.option("--yes-delete-everything", is_flag=True, help="Required confirmation flag.")
    def reset_cmd(yes_delete_everything):
        """DANGER: drop all tables and re-seed. Refuses to run in production."""
        if current_app.config.get("ENV_NAME") == "production":
            raise click.ClickException("reset-demo is disabled when VELORA_ENV=production.")
        if not yes_delete_everything:
            raise click.ClickException("Pass --yes-delete-everything to confirm deleting ALL data.")
        from .seed import seed
        db.drop_all()
        db.session.execute(db.text("DROP TABLE IF EXISTS alembic_version"))
        db.session.commit()
        init_database()
        seed()
        click.echo("Demo database reset and re-seeded.")

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
