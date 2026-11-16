"""Fill in missing or broken product photos from the internet.

Uses Pexels (professional model photos) when a key has been added, otherwise Openverse (free, no key).
Used by Seller studio -> Products -> "Fill missing & broken photos" and by the `fill-photos` command that
start.bat / start.sh run, so photos appear without anyone having to click anything.
"""
from dataclasses import dataclass, field

from flask import has_request_context

from ..extensions import db
from ..models import PRODUCT_ARCHIVED, Product, ProductImage, StoreSetting
from ..photos import credit_key, product_query, setting_key
from ..security import audit
from . import openverse, pexels, photo_check
from .uploads import UploadError, delete_upload, save_image_bytes


@dataclass
class FillResult:
    source: str = ""
    needed: int = 0
    done: list = field(default_factory=list)
    skipped: list = field(default_factory=list)
    left: int = 0
    error: str = ""


def provider():
    """(module, label): Pexels if a key is saved, else the keyless Openverse."""
    return (pexels, "Pexels") if pexels.api_key() else (openverse, "Openverse")


def apply_photo(target, filename, credit):
    """Make `filename` the photo for a site spot, or the cover image of a product."""
    kind, obj = target[0], target[1]
    if kind == "slot":
        for key, value in ((setting_key(obj), filename), (credit_key(obj), credit)):
            row = db.session.get(StoreSetting, key)
            if row is None:
                db.session.add(StoreSetting(key=key, value=value))
                continue
            if key == setting_key(obj):
                delete_upload(row.value)  # drop the photo this one replaces
            row.value = value
    else:
        image = ProductImage(filename=filename, alt=obj.name, credit=credit)
        ordered = [image] + list(obj.images)  # the new photo becomes the cover
        obj.images.append(image)
        for pos, img in enumerate(ordered):
            img.position = pos
        obj.images.sort(key=lambda i: i.position)


def pick_photo(query, used, source=pexels):
    """The best unused photo for a search: a portrait one if possible, looking at two pages of results."""
    candidates = []
    for page in (1, 2):
        photos, total = source.search(query, page=page, per_page=15)
        candidates += [p for p in photos if p.id not in used and p.id not in {c.id for c in candidates}]
        if any(p.height >= p.width * 1.2 for p in candidates) or page * 15 >= total:
            break
    return next((p for p in candidates if p.height >= p.width * 1.2), None) or (candidates[0] if candidates else None)


def fill_products(limit=30, actor=None):
    """Give products with a missing or broken photo a matching one. Raises PexelsError if the source is unreachable
    before anything was done; otherwise errors stop the run and are reported in the result."""
    source, label = provider()
    res = FillResult(source=label)
    products = Product.query.filter(Product.status != PRODUCT_ARCHIVED).order_by(Product.name).all()
    status = photo_check.check_remote(img.url for p in products for img in p.images if img.url and not img.filename)
    need = [p for p in products if not photo_check.working_images(p, status)]
    need.sort(key=lambda p: (bool(p.images), p.name))  # no photo at all first, then broken ones
    res.needed = len(need)
    used = set()
    try:
        for product in need[:limit]:
            pick = pick_photo(product_query(product), used, source)
            if pick is None:
                res.skipped.append(product.name)
                continue
            filename = save_image_bytes(source.download(pick))
            working = photo_check.working_images(product, status)
            for img in [i for i in product.images if i not in working]:
                product.images.remove(img)  # dead links go
                db.session.delete(img)
            apply_photo(("product", product), filename, pick.credit)
            used.add(pick.id)
            if has_request_context():
                audit(f"photo.{label.lower()}", "product", product.id, f"{product.name} ← {label} #{pick.id} (fill missing)")
            db.session.commit()
            res.done.append(product.name)
    except (pexels.PexelsError, UploadError) as exc:
        db.session.rollback()
        if not res.done and not isinstance(exc, UploadError):
            raise
        res.error = str(exc)
    res.left = max(0, len(need) - limit)
    return res
