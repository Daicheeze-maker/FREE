"""Open Food Facts integration (https://world.openfoodfacts.org/data).

Read-only usage, no authentication. Requests identify the app with a descriptive
User-Agent ("AppName/Version (contact)") as the OFF usage policy asks, and searches
are kept to explicit staff actions to stay well within the published rate limits.
"""
import re
import time
from dataclasses import dataclass, field

import requests
from flask import current_app

from ..extensions import db
from ..models import PRODUCT_DRAFT, Product, ProductImage, utcnow
from . import api_health

FIELDS = ("code,product_name,product_name_en,generic_name,brands,categories,quantity,"
          "image_front_url,image_url,ingredients_text,ingredients_text_en,allergens,"
          "nutriscore_grade,nutriments,countries")

NUTRIENTS = [  # (OFF key, label, unit)
    ("energy-kcal_100g", "Energy", "kcal"),
    ("fat_100g", "Fat", "g"),
    ("saturated-fat_100g", "Saturated fat", "g"),
    ("carbohydrates_100g", "Carbohydrates", "g"),
    ("sugars_100g", "Sugars", "g"),
    ("fiber_100g", "Fibre", "g"),
    ("proteins_100g", "Protein", "g"),
    ("salt_100g", "Salt", "g"),
]

BARCODE_RE = re.compile(r"^\d{6,14}$")


class OFFUnavailable(Exception):
    pass


@dataclass
class OFFProduct:
    barcode: str
    name: str
    brand: str = ""
    categories: str = ""
    quantity: str = ""
    image_url: str | None = None
    ingredients: str = ""
    allergens: str = ""
    nutriscore: str | None = None
    nutrition: dict = field(default_factory=dict)

    @property
    def complete(self):
        return bool(self.name and self.image_url and self.ingredients)


def _clean(value, limit):
    if not isinstance(value, str):
        return ""
    value = re.sub(r"\s+", " ", value).strip()
    return value[:limit]


def _https_image(url):
    if isinstance(url, str) and url.startswith("https://") and len(url) <= 500:
        return url
    if isinstance(url, str) and url.startswith("http://") and len(url) <= 499:
        return "https://" + url[len("http://"):]
    return None


def normalize(raw):
    """Validate & normalize one OFF product dict. Returns OFFProduct or None if unusable."""
    if not isinstance(raw, dict):
        return None
    code = str(raw.get("code") or "").strip()
    if not BARCODE_RE.match(code):
        return None
    name = _clean(raw.get("product_name") or raw.get("product_name_en") or raw.get("generic_name"), 200)
    if not name:
        return None
    brand = _clean((raw.get("brands") or "").split(",")[0], 120)
    nutr_raw = raw.get("nutriments") if isinstance(raw.get("nutriments"), dict) else {}
    nutrition = {}
    for key, label, unit in NUTRIENTS:
        val = nutr_raw.get(key)
        try:
            num = round(float(val), 2)
        except (TypeError, ValueError):
            continue
        if 0 <= num < 10000:
            nutrition[key] = {"label": label, "value": num, "unit": unit}
    grade = _clean(raw.get("nutriscore_grade"), 2).lower()
    allergens = ", ".join(a.split(":")[-1].replace("-", " ")
                          for a in _clean(raw.get("allergens"), 300).split(",") if a.strip())
    return OFFProduct(
        barcode=code,
        name=name,
        brand=brand,
        categories=_clean(raw.get("categories"), 400),
        quantity=_clean(raw.get("quantity"), 60),
        image_url=_https_image(raw.get("image_front_url") or raw.get("image_url")),
        ingredients=_clean(raw.get("ingredients_text_en") or raw.get("ingredients_text"), 4000),
        allergens=allergens[:300],
        nutriscore=grade if grade in {"a", "b", "c", "d", "e"} else None,
        nutrition=nutrition,
    )


def _get(path, params=None):
    cfg = current_app.config
    started = time.monotonic()
    try:
        resp = requests.get(
            cfg["OFF_BASE_URL"].rstrip("/") + path, params=params,
            headers={"User-Agent": api_health.user_agent(), "Accept": "application/json"},
            timeout=cfg["HTTP_TIMEOUT"],
        )
        if resp.status_code == 429:
            raise OFFUnavailable("Open Food Facts rate limit reached — please wait a minute and retry.")
        resp.raise_for_status()
        data = resp.json()
    except OFFUnavailable as exc:
        api_health.record_error(api_health.OFF, str(exc))
        raise
    except (requests.RequestException, ValueError) as exc:
        api_health.record_error(api_health.OFF, f"{type(exc).__name__}: {exc}")
        raise OFFUnavailable("Open Food Facts is unreachable right now. Your local catalog is unaffected.") from exc
    api_health.record_success(api_health.OFF, int((time.monotonic() - started) * 1000))
    return data


def search(query, page=1, page_size=24):
    """Full-text product search. Returns (products: list[OFFProduct], total_count: int)."""
    query = _clean(query, 100)
    if len(query) < 2:
        return [], 0
    data = _get("/cgi/search.pl", {
        "search_terms": query, "search_simple": 1, "action": "process", "json": 1,
        "page": max(1, int(page)), "page_size": min(max(1, int(page_size)), 50), "fields": FIELDS,
    })
    raw_products = data.get("products") if isinstance(data, dict) else None
    if not isinstance(raw_products, list):
        return [], 0
    products = [p for p in (normalize(r) for r in raw_products) if p]
    try:
        count = int(data.get("count") or len(products))
    except (TypeError, ValueError):
        count = len(products)
    return products, count


def get_product(barcode):
    barcode = str(barcode).strip()
    if not BARCODE_RE.match(barcode):
        raise ValueError("Invalid barcode")
    data = _get(f"/api/v2/product/{barcode}.json", {"fields": FIELDS})
    if not isinstance(data, dict) or data.get("status") != 1:
        return None
    raw = data.get("product") or {}
    raw.setdefault("code", data.get("code", barcode))
    return normalize(raw)


def import_product(barcode, category, price_minor, stock, status=PRODUCT_DRAFT):
    """Fetch authoritative data from OFF (never trusting browser-submitted fields) and store it."""
    from .catalog import unique_slug, next_sku

    if Product.query.filter_by(off_barcode=str(barcode)).first():
        raise ValueError("This product has already been imported.")
    off = get_product(barcode)
    if off is None:
        raise ValueError("Open Food Facts has no product with that barcode.")
    desc_bits = [f"{off.name} by {off.brand}." if off.brand else f"{off.name}."]
    if off.quantity:
        desc_bits.append(f"Pack size: {off.quantity}.")
    if off.categories:
        desc_bits.append("Listed on Open Food Facts under " + ", ".join(off.categories.split(",")[:3]).strip() + ".")
    product = Product(
        name=off.name, slug=unique_slug(off.name), sku=next_sku("OFF"),
        brand=off.brand or "Independent", category=category,
        short_description=(f"{off.brand} · {off.quantity}" if off.brand and off.quantity else off.quantity or off.brand or "Imported from Open Food Facts")[:300],
        description=" ".join(desc_bits), price_minor=price_minor, stock=stock, status=status,
        size_label=off.quantity or None, source="openfoodfacts", off_barcode=off.barcode,
        ingredients=off.ingredients or None, allergens=off.allergens or None,
        nutriscore=off.nutriscore, nutrition_json=off.nutrition or None,
        off_categories=off.categories or None, synced_at=utcnow(),
    )
    if off.image_url:
        product.images.append(ProductImage(url=off.image_url, alt=off.name, credit="Open Food Facts (CC BY-SA)"))
    db.session.add(product)
    return product
