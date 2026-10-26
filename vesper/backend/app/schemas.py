import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

Family = Literal["Floral", "Woody", "Amber", "Fresh", "Gourmand", "Chypre"]
Concentration = Literal["EDT", "EDP", "Parfum"]


class SellerIn(BaseModel):
    id: str = Field(pattern=r"^[a-z0-9-]{2,40}$")
    name: str = Field(min_length=2, max_length=80)
    tagline: str = Field(max_length=160)
    description: str
    origin: str
    founded: int = Field(ge=1700, le=2100)
    accent: str = Field(pattern=r"^#[0-9a-fA-F]{6}$")
    bottle: Literal["block", "dome", "column", "facet"]


class ProductIn(BaseModel):
    id: str = Field(pattern=r"^[a-z0-9-]{2,60}$")
    seller_id: str
    name: str = Field(min_length=2, max_length=80)
    price_centavos: int = Field(gt=0, le=10_000_000)
    description: str
    top_notes: list[str] = Field(min_length=1)
    heart_notes: list[str] = Field(min_length=1)
    base_notes: list[str] = Field(min_length=1)
    size_ml: int = Field(gt=0, le=1000)
    family: Family
    concentration: Concentration
    stock: int = Field(ge=0)
    hue: str = Field(pattern=r"^#[0-9a-fA-F]{6}$")
    bestseller: bool = False


class SellerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    tagline: str
    description: str
    origin: str
    founded: int
    accent: str
    bottle: str


class ProductOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    seller_id: str
    name: str
    price_centavos: int
    description: str
    top_notes: list[str]
    heart_notes: list[str]
    base_notes: list[str]
    size_ml: int
    family: str
    concentration: str
    stock: int
    hue: str
    bestseller: bool
    seller: SellerOut


class QuantityIn(BaseModel):
    quantity: int = Field(ge=1, le=10)


class CartItemIn(QuantityIn):
    product_id: str


class CustomerIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    phone: str
    address: str = Field(min_length=10, max_length=500)

    @field_validator("name", "address")
    @classmethod
    def strip(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 2:
            raise ValueError("is required")
        return v

    @field_validator("phone")
    @classmethod
    def ph_phone(cls, v: str) -> str:
        digits = re.sub(r"[\s-]", "", v)
        # Philippine mobile (09XXXXXXXXX / +639XXXXXXXXX) or landline-ish numbers.
        if not re.fullmatch(r"(\+63|0)\d{9,10}", digits):
            raise ValueError("enter a Philippine number, e.g. 0917 123 4567")
        return digits


class CheckoutIn(BaseModel):
    cart_id: str
    customer: CustomerIn
    payment_method: Literal["card", "gcash", "paymaya"]


class MockOutcomeIn(BaseModel):
    outcome: Literal["paid", "failed"]


class NewsletterIn(BaseModel):
    email: EmailStr
