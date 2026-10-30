import pytest
from flask.testing import FlaskClient

from velora import create_app
from velora.extensions import db
from velora.models import Address, Product, User
from velora.seed import seed


class IsolatedClient(FlaskClient):
    """Run every request in a fresh app context (fresh `g` and DB session), like production,
    even though the test itself holds an app context open for direct DB access."""

    def open(self, *args, **kwargs):
        with self.application.app_context():
            return super().open(*args, **kwargs)


@pytest.fixture()
def app(tmp_path):
    app = create_app("testing", SQLALCHEMY_DATABASE_URI=f"sqlite:///{tmp_path / 'test.db'}",
                     UPLOAD_FOLDER=str(tmp_path / "uploads"))
    app.test_client_class = IsolatedClient
    with app.app_context():
        db.create_all()
        seed()
        yield app
        db.session.remove()


@pytest.fixture()
def client(app):
    return app.test_client()


def login(client, email, password):
    return client.post("/account/login", data={"email": email, "password": password})


@pytest.fixture()
def customer(client):
    assert login(client, "customer@velora.example", "Customer123!").status_code == 302
    return client


@pytest.fixture()
def seller(client):
    assert login(client, "seller@velora.example", "Seller123!").status_code == 302
    return client


@pytest.fixture()
def admin(client):
    assert login(client, "admin@velora.example", "Admin123!").status_code == 302
    return client


def get_user(email):
    return User.query.filter_by(email=email).first()


def in_stock_product(min_stock=5):
    return Product.query.filter(Product.stock >= min_stock, Product.status == "active").order_by(Product.id).first()


def default_address(user):
    return Address.query.filter_by(user_id=user.id, is_default=True).first()
