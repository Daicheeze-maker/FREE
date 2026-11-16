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
        seed(demo_accounts=True)
        yield app
        db.session.remove()


@pytest.fixture()
def client(app):
    return app.test_client()


def login(client, email, password):
    return client.post("/account/login", data={"email": email, "password": password})


@pytest.fixture()
def customer(client):
    assert login(client, "buyer1@velora.example", "Buyer123!").status_code == 302
    return client


@pytest.fixture()
def seller(client):
    """Seller profile of buyer 1 (each buyer has a linked seller profile; switch to it after sign-in)."""
    assert login(client, "buyer1@velora.example", "Buyer123!").status_code == 302
    assert client.post("/account/switch-profile").status_code == 302
    return client


@pytest.fixture()
def admin(client):
    assert login(client, "admin@velora.example", "Admin123!").status_code == 302
    return client


def get_user(email):
    return User.query.filter_by(email=email).first()


def in_stock_product(min_stock=5):
    """A watch the tests can put straight into the bag: it has its size, colour and engraving options switched off."""
    p = (Product.query.filter(Product.stock >= min_stock, Product.status == "active").order_by(Product.id).first())
    if p.sizes or p.colors or p.engraving_fee_minor is not None:
        p.sizes = p.colors = p.engraving_fee_minor = None
        db.session.commit()
    return p


def optioned_product(min_stock=5):
    """A watch that has sizes, colours and engraving (the normal case in the store)."""
    return (Product.query.filter(Product.stock >= min_stock, Product.status == "active", Product.sizes.isnot(None),
                                 Product.colors.isnot(None), Product.engraving_fee_minor.isnot(None))
            .order_by(Product.id).first())


sized_product = optioned_product


def default_address(user):
    return Address.query.filter_by(user_id=user.id, is_default=True).first()
