"""Server-side pricing: discounts, shipping and totals. Browser-submitted amounts are never used."""
from dataclasses import dataclass

from ..models import DiscountCode, get_int_setting, utcnow
from ..money import fmt_minor, percent_of


class DiscountError(ValueError):
    pass


@dataclass
class Totals:
    subtotal_minor: int
    discount_minor: int
    shipping_minor: int
    total_minor: int
    discount: DiscountCode | None
    free_shipping_threshold_minor: int

    @property
    def to_free_shipping_minor(self):
        return max(0, self.free_shipping_threshold_minor - (self.subtotal_minor - self.discount_minor))


def find_discount(code):
    if not code:
        return None
    return DiscountCode.query.filter(DiscountCode.code == code.strip().upper()[:40]).first()


def validate_discount(discount, subtotal_minor):
    if discount is None:
        raise DiscountError("That code isn't valid.")
    now = utcnow()
    if not discount.is_active:
        raise DiscountError("That code is no longer active.")
    if discount.starts_at and now < discount.starts_at:
        raise DiscountError("That code isn't active yet.")
    if discount.ends_at and now > discount.ends_at:
        raise DiscountError("That code has expired.")
    if discount.max_uses is not None and discount.used_count >= discount.max_uses:
        raise DiscountError("That code has reached its usage limit.")
    if subtotal_minor < discount.min_subtotal_minor:
        raise DiscountError(f"Spend at least {fmt_minor(discount.min_subtotal_minor)} to use this code.")
    return discount


def discount_amount(discount, subtotal_minor):
    if discount is None:
        return 0
    if discount.kind == "percent":
        amount = percent_of(subtotal_minor, min(discount.value, 90))
    else:
        amount = discount.value
    return max(0, min(amount, subtotal_minor))


def shipping_for(net_subtotal_minor, has_items=True):
    if not has_items:
        return 0
    threshold = get_int_setting("free_shipping_threshold_minor")
    if net_subtotal_minor >= threshold:
        return 0
    return get_int_setting("shipping_flat_minor")


def compute_totals(subtotal_minor, code=None, has_items=True):
    """Compute totals. Invalid codes are silently dropped here; use validate_discount for feedback."""
    discount = find_discount(code) if code else None
    if discount is not None:
        try:
            validate_discount(discount, subtotal_minor)
        except DiscountError:
            discount = None
    disc = discount_amount(discount, subtotal_minor)
    shipping = shipping_for(subtotal_minor - disc, has_items)
    return Totals(subtotal_minor, disc, shipping, subtotal_minor - disc + shipping, discount,
                  get_int_setting("free_shipping_threshold_minor"))
