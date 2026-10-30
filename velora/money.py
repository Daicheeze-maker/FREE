"""Money helpers. All stored amounts are integer minor units (centavos) of the base currency.

Converted amounts are for display only and are computed with Decimal.
"""
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

SYMBOLS = {"PHP": "₱", "USD": "$", "EUR": "€", "GBP": "£", "JPY": "¥", "SGD": "S$", "AUD": "A$"}
ZERO_DECIMAL = {"JPY", "KRW", "IDR", "ISK", "HUF"}


def to_minor(value) -> int:
    """Parse a user-entered major-unit amount ("1,299.50") into minor units. Raises ValueError."""
    try:
        d = Decimal(str(value).replace(",", "").strip())
    except (InvalidOperation, AttributeError):
        raise ValueError("Enter a valid amount")
    if d.is_nan() or d.is_infinite() or d < 0:
        raise ValueError("Amount must be zero or more")
    return int((d * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def to_major(minor: int) -> Decimal:
    return (Decimal(int(minor)) / 100).quantize(Decimal("0.01"))


def convert(minor: int, rate: Decimal, currency: str) -> Decimal:
    places = Decimal("1") if currency in ZERO_DECIMAL else Decimal("0.01")
    return (to_major(minor) * Decimal(rate)).quantize(places, rounding=ROUND_HALF_UP)


def fmt(amount: Decimal, currency: str) -> str:
    symbol = SYMBOLS.get(currency, currency + " ")
    if currency in ZERO_DECIMAL:
        return f"{symbol}{amount:,.0f}"
    return f"{symbol}{amount:,.2f}"


def fmt_minor(minor: int, currency: str = "PHP") -> str:
    return fmt(to_major(minor), currency)


def percent_of(minor: int, pct: int) -> int:
    """pct% of an amount, rounded half-up to the nearest minor unit."""
    return int((Decimal(int(minor)) * Decimal(pct) / 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
