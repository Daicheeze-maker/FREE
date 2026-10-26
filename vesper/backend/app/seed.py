"""Create tables and seed the 4 fictional sellers and 20 products. Run: python -m app.seed [--reset]"""
import sys

from sqlalchemy import func, select

from .db import Base, SessionLocal, engine
from .models import Seller
from .schemas import ProductIn, SellerIn
from .seed_data import PRODUCTS, SELLERS
from .services.catalog import create_product, create_seller


def seed(db) -> bool:
    if db.scalar(select(func.count(Seller.id))):
        return False
    # Goes through the same limit-enforcing services as the API.
    for s in SELLERS:
        create_seller(db, SellerIn(**s))
    for p in PRODUCTS:
        create_product(db, ProductIn(**p))
    db.commit()
    return True


def init_db(bind=engine, reset=False):
    if reset:
        Base.metadata.drop_all(bind)
    Base.metadata.create_all(bind)


if __name__ == "__main__":
    init_db(reset="--reset" in sys.argv)
    with SessionLocal() as db:
        print("Seeded 4 sellers / 20 products." if seed(db) else "Database already seeded.")
