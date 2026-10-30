import io

from PIL import Image
from sqlalchemy import inspect

from velora import create_app
from velora.extensions import db
from velora.models import AuditLog, Category, DiscountCode, Product, StoreSetting, User


def _png_bytes():
    buf = io.BytesIO()
    Image.new("RGB", (40, 40), (30, 107, 82)).save(buf, "PNG")
    buf.seek(0)
    return buf


def _product_form(**over):
    data = {"name": "Test Granola", "brand": "Tester", "category_id": Category.query.first().id,
            "short_description": "Crunchy", "description": "A test product.", "price": "199.50",
            "stock": "10", "status": "active"}
    data.update(over)
    return data


def test_seller_creates_product_with_valid_upload(seller, app):
    data = _product_form()
    data["image"] = (_png_bytes(), "photo.png")
    r = seller.post("/seller/products/new", data=data, content_type="multipart/form-data")
    assert r.status_code == 302
    p = Product.query.filter_by(name="Test Granola").first()
    assert p.price_minor == 19950
    fname = p.images[0].filename
    assert fname.endswith(".webp") and "photo" not in fname
    assert seller.get(f"/media/{fname}").status_code == 200
    assert AuditLog.query.filter_by(action="product.create").count() == 1


def test_invalid_uploads_rejected(seller):
    cases = [(io.BytesIO(b"<?php echo 'hi'; ?>"), "shell.php"),
             (io.BytesIO(b"not really an image"), "fake.png"),
             (io.BytesIO(b""), "empty.jpg")]
    for stream, name in cases:
        data = _product_form(name=f"Upload {name}")
        data["image"] = (stream, name)
        r = seller.post("/seller/products/new", data=data, content_type="multipart/form-data")
        assert r.status_code == 400, name
        assert Product.query.filter_by(name=f"Upload {name}").first() is None


def test_oversized_upload_rejected(seller, app):
    app.config["MAX_CONTENT_LENGTH"] = 1024
    data = _product_form(name="Huge")
    data["image"] = (io.BytesIO(b"x" * 5000), "big.png")
    r = seller.post("/seller/products/new", data=data, content_type="multipart/form-data")
    assert r.status_code == 413


def test_media_path_traversal_blocked(client):
    assert client.get("/media/../velora.db").status_code == 404
    assert client.get("/media/.env").status_code == 404


def test_product_validation(seller):
    r = seller.post("/seller/products/new", data=_product_form(price="-5", compare_at="1"))
    assert r.status_code == 200 and "field__error" in r.get_data(as_text=True)


def test_archive_and_restore(seller):
    p = Product.query.first()
    seller.post(f"/seller/products/{p.id}/status/archived")
    db.session.refresh(p)
    assert p.status == "archived"
    seller.post(f"/seller/products/{p.id}/status/active")
    db.session.refresh(p)
    assert p.status == "active"


def test_restock(seller):
    p = Product.query.filter_by(stock=0).first()
    seller.post(f"/seller/inventory/{p.id}", data={"add": "15"})
    db.session.refresh(p)
    assert p.stock == 15


def test_discount_crud(seller):
    r = seller.post("/seller/discounts/new", data={"code": "test20", "kind": "percent", "value": "20", "is_active": "y"})
    assert r.status_code == 302
    d = DiscountCode.query.filter_by(code="TEST20").first()
    assert d and d.value == 20
    r = seller.post("/seller/discounts/new", data={"code": "BAD", "kind": "percent", "value": "150"})
    assert r.status_code == 200 and DiscountCode.query.filter_by(code="BAD").first() is None


def test_category_with_products_cannot_be_deleted(seller):
    c = Category.query.first()
    seller.post(f"/seller/categories/{c.id}/delete")
    assert db.session.get(Category, c.id) is not None


def test_csv_exports(seller):
    r = seller.get("/seller/export/products.csv")
    assert r.status_code == 200 and r.mimetype == "text/csv" and "sku,name" in r.get_data(as_text=True)
    r = seller.get("/seller/export/orders.csv")
    assert "order,created_at" in r.get_data(as_text=True)


def test_review_moderation(seller):
    from velora.models import ProductReview
    rv = ProductReview.query.first()
    seller.post(f"/seller/reviews/{rv.id}/toggle")
    db.session.refresh(rv)
    assert rv.is_hidden


def test_admin_settings_change_shipping(admin):
    r = admin.post("/admin/settings", data={"shipping_flat": "99.00", "free_shipping_threshold": "1000",
                                           "low_stock_threshold": "3", "store_announcement": "Hi",
                                           "support_email": "help@example.com"})
    assert r.status_code == 302
    assert db.session.get(StoreSetting, "shipping_flat_minor").value == "9900"
    from velora.services.pricing import compute_totals
    assert compute_totals(50000).shipping_minor == 9900


def test_admin_pages_render(admin):
    for url in ("/admin/", "/admin/users", "/admin/reports", "/admin/reports?days=7", "/admin/settings",
                "/admin/api-health", "/admin/audit", "/seller/", "/seller/import"):
        assert admin.get(url).status_code == 200, url


# ------------------------------------------------------------ database init

def test_database_initialization_via_migrations(tmp_path):
    from velora.cli import init_database
    from velora.seed import seed
    app = create_app("testing", SQLALCHEMY_DATABASE_URI=f"sqlite:///{tmp_path / 'fresh.db'}")
    with app.app_context():
        init_database()
        tables = set(inspect(db.engine).get_table_names())
        for t in ("user", "product", "order", "order_item", "payment_record", "exchange_rate_cache", "audit_log"):
            assert t in tables
        assert seed() is True
        n = User.query.count()
        assert seed() is False  # never re-seeds / resets existing data
        assert User.query.count() == n
        init_database()  # idempotent upgrade
        assert User.query.count() == n


def test_cli_seed_is_non_destructive(tmp_path):
    app = create_app("testing", SQLALCHEMY_DATABASE_URI=f"sqlite:///{tmp_path / 'cli.db'}")
    runner = app.test_cli_runner()
    assert "Seeded" in runner.invoke(args=["seed"]).output
    assert "skipped" in runner.invoke(args=["seed"]).output
    assert runner.invoke(args=["reset-demo"]).exit_code != 0  # requires explicit flag


def test_production_requires_secret_key(monkeypatch):
    monkeypatch.delenv("SECRET_KEY", raising=False)
    import pytest
    from velora.config import ProductionConfig
    monkeypatch.setattr(ProductionConfig, "SECRET_KEY", "")
    with pytest.raises(RuntimeError):
        create_app("production")
