"""Frankfurter exchange rates (https://frankfurter.dev), fetched server-side and cached."""
import time
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

import httpx

from ..config import env

SUPPORTED = {"PHP", "USD"}
SYMBOLS = {"PHP": "₱", "USD": "$"}
CACHE_TTL = 6 * 3600  # Frankfurter publishes once per working day
transport: httpx.BaseTransport | None = None  # tests inject httpx.MockTransport here
_cache: dict[tuple[str, str], tuple[float, dict]] = {}


class RateUnavailable(Exception):
    pass


def _parse(payload, base: str, quote: str) -> tuple[Decimal, str]:
    # v2 /rates returns a list of {date, base, quote, rate}; v1 /latest returns {date, rates: {QUOTE: rate}}.
    if isinstance(payload, list):
        row = next((r for r in payload if r.get("base") == base and r.get("quote") == quote), None)
        if row is None:
            raise RateUnavailable(f"No {base}->{quote} rate in response")
        rate, date = row.get("rate"), row.get("date")
    elif isinstance(payload, dict) and isinstance(payload.get("rates"), dict):
        rate, date = payload["rates"].get(quote), payload.get("date")
    else:
        raise RateUnavailable("Unexpected response shape")
    try:
        rate = Decimal(str(rate))
    except (InvalidOperation, TypeError):
        raise RateUnavailable("Rate is not a number")
    if rate <= 0 or not date:
        raise RateUnavailable("Rate missing or invalid")
    return rate, date


def get_rate(base: str, quote: str) -> dict:
    base, quote = base.upper(), quote.upper()
    if base not in SUPPORTED or quote not in SUPPORTED:
        raise ValueError(f"Unsupported currency. Supported: {', '.join(sorted(SUPPORTED))}")
    if base == quote:
        return {"base": base, "quote": quote, "rate": "1", "date": None, "source": "identity", "stale": False}

    key = (base, quote)
    cached = _cache.get(key)
    if cached and time.time() - cached[0] < CACHE_TTL:
        return {**cached[1], "source": "cache", "stale": False}

    url = env("FRANKFURTER_BASE_URL", "https://api.frankfurter.dev/v2").rstrip("/") + "/rates"
    try:
        with httpx.Client(transport=transport, timeout=float(env("FRANKFURTER_TIMEOUT", "5"))) as client:
            res = client.get(url, params={"base": base, "quotes": quote})
            res.raise_for_status()
            rate, date = _parse(res.json(), base, quote)
    except (httpx.HTTPError, ValueError, RateUnavailable) as exc:
        if cached:  # serve the last good rate rather than nothing
            return {**cached[1], "source": "cache", "stale": True}
        raise RateUnavailable(str(exc) or exc.__class__.__name__) from exc

    data = {"base": base, "quote": quote, "rate": str(rate), "date": date}
    _cache[key] = (time.time(), data)
    return {**data, "source": "live", "stale": False}


def convert_centavos(amount_centavos: int, rate: str | Decimal) -> Decimal:
    """PHP centavos -> target currency major units, rounded half-up to 2 decimals."""
    return (Decimal(amount_centavos) * Decimal(rate) / 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def format_money(amount: Decimal, currency: str) -> str:
    return f"{SYMBOLS[currency]}{amount:,.2f}"
