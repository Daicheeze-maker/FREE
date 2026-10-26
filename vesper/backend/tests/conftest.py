import os

os.environ["AUTO_SEED"] = "0"  # tests build their own throwaway DB

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app.db import get_db, make_engine
from app.main import app
from app.seed import init_db, seed
from app.services import currency, paymongo

CUSTOMER = {"name": "Maria Santos", "email": "maria@example.com", "phone": "0917 123 4567",
            "address": "12 Acacia St, Brgy. San Antonio, Pasig City, Metro Manila 1605"}


@pytest.fixture
def SessionTest(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path / 'test.db'}")
    init_db(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    with Session() as db:
        seed(db)
    yield Session
    engine.dispose()


@pytest.fixture
def client(SessionTest, monkeypatch):
    def _db():
        with SessionTest() as db:
            yield db

    app.dependency_overrides[get_db] = _db
    for var in ("PAYMONGO_SECRET_KEY", "PAYMONGO_WEBHOOK_SECRET", "ADMIN_TOKEN", "FRANKFURTER_BASE_URL"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("PAYMENT_MODE", "mock")
    currency._cache.clear()
    currency.transport = None
    paymongo.transport = None
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
    currency.transport = None
    paymongo.transport = None


@pytest.fixture
def cart(client):
    return client.post("/api/carts").json()["id"]


def add(client, cart_id, product_id, qty=1):
    return client.post(f"/api/carts/{cart_id}/items", json={"product_id": product_id, "quantity": qty})
