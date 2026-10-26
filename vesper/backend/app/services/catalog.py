from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import MAX_PRODUCTS_PER_SELLER, MAX_SELLERS
from ..models import Product, Seller
from ..schemas import ProductIn, SellerIn


def create_seller(db: Session, data: SellerIn) -> Seller:
    if db.scalar(select(func.count(Seller.id))) >= MAX_SELLERS:
        raise HTTPException(409, f"Marketplace is limited to {MAX_SELLERS} sellers.")
    if db.get(Seller, data.id) or db.scalar(select(Seller).where(Seller.name == data.name)):
        raise HTTPException(409, "A seller with this id or name already exists.")
    seller = Seller(**data.model_dump())
    db.add(seller)
    db.flush()
    return seller


def create_product(db: Session, data: ProductIn) -> Product:
    if not db.get(Seller, data.seller_id):
        raise HTTPException(404, f"Seller '{data.seller_id}' does not exist.")
    if db.get(Product, data.id):
        raise HTTPException(409, "A product with this id already exists.")
    count = db.scalar(select(func.count(Product.id)).where(Product.seller_id == data.seller_id))
    if count >= MAX_PRODUCTS_PER_SELLER:
        raise HTTPException(409, f"Each seller may list at most {MAX_PRODUCTS_PER_SELLER} products.")
    product = Product(**data.model_dump())
    db.add(product)
    db.flush()
    return product


SORTS = {
    "price_asc": Product.price_centavos.asc(),
    "price_desc": Product.price_centavos.desc(),
    "name_asc": Product.name.asc(),
    "name_desc": Product.name.desc(),
}


def search_products(db: Session, q=None, seller=None, family=None, min_price=None, max_price=None, sort=None):
    stmt = select(Product).join(Seller)
    if q:
        like = f"%{q.strip().lower()}%"
        stmt = stmt.where(func.lower(Product.name).like(like) | func.lower(Seller.name).like(like))
    if seller:
        stmt = stmt.where(Product.seller_id.in_(seller))
    if family:
        stmt = stmt.where(Product.family.in_(family))
    if min_price is not None:
        stmt = stmt.where(Product.price_centavos >= min_price * 100)
    if max_price is not None:
        stmt = stmt.where(Product.price_centavos <= max_price * 100)
    stmt = stmt.order_by(SORTS.get(sort, Product.seller_id.asc()), Product.id)
    return list(db.scalars(stmt))
