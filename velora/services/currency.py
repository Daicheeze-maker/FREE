"""Frankfurter exchange-rate integration (https://frankfurter.dev/).

Rates are cached in ExchangeRateCache. Converted prices are display-only: orders are
always charged in the base currency.
"""
import time
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal, InvalidOperation

import requests
from flask import current_app, session

from ..extensions import db
from ..models import ExchangeRateCache, utcnow
from ..money import convert, fmt, fmt_minor
from . import api_health


class RatesUnavailable(Exception):
    pass


@dataclass
class FxQuote:
    currency: str
    rate: Decimal
    rate_date: str | None
    fetched_at: object
    stale: bool


def fetch_rates(base, targets):
    """Call Frankfurter /latest. Returns (rates: dict[str, Decimal], date: str)."""
    cfg = current_app.config
    url = f"{cfg['FRANKFURTER_BASE_URL'].rstrip('/')}/latest"
    started = time.monotonic()
    try:
        resp = requests.get(
            url, params={"base": base, "symbols": ",".join(sorted(targets))},
            headers={"User-Agent": api_health.user_agent(), "Accept": "application/json"},
            timeout=cfg["HTTP_TIMEOUT"],
        )
        resp.raise_for_status()
        payload = resp.json()
        raw_rates = payload["rates"]
        rates = {}
        for code, value in raw_rates.items():
            # parse via str() so we never carry binary float error into Decimal
            rate = Decimal(str(value))
            if rate <= 0:
                raise ValueError(f"non-positive rate for {code}")
            rates[code.upper()] = rate
        if payload.get("base", base).upper() != base.upper():
            raise ValueError("unexpected base currency in response")
    except (requests.RequestException, ValueError, KeyError, TypeError, InvalidOperation, AttributeError) as exc:
        api_health.record_error(api_health.FRANKFURTER, f"{type(exc).__name__}: {exc}")
        raise RatesUnavailable(str(exc)) from exc
    api_health.record_success(api_health.FRANKFURTER, int((time.monotonic() - started) * 1000))
    return rates, payload.get("date")


def refresh_cache(force=False):
    """Refresh all display currencies in one request. Returns number of rates stored."""
    cfg = current_app.config
    base = cfg["BASE_CURRENCY"]
    targets = [c for c in cfg["DISPLAY_CURRENCIES"] if c != base]
    if not force and api_health.in_backoff(api_health.FRANKFURTER):
        raise RatesUnavailable("Exchange-rate service recently failed; retrying later")
    rates, rate_date = fetch_rates(base, targets)
    now = utcnow()
    for code, rate in rates.items():
        row = ExchangeRateCache.query.filter_by(base=base, target=code).first()
        if row is None:
            row = ExchangeRateCache(base=base, target=code)
            db.session.add(row)
        row.rate, row.rate_date, row.fetched_at = str(rate), rate_date, now
    db.session.commit()
    return len(rates)


def get_quote(currency):
    """Return an FxQuote for base->currency, or None if no rate is available at all."""
    cfg = current_app.config
    base = cfg["BASE_CURRENCY"]
    if currency == base:
        return None
    row = ExchangeRateCache.query.filter_by(base=base, target=currency).first()
    ttl = timedelta(hours=cfg["FX_CACHE_HOURS"])
    if row is None or utcnow() - row.fetched_at > ttl:
        try:
            refresh_cache()
            row = ExchangeRateCache.query.filter_by(base=base, target=currency).first()
        except RatesUnavailable:
            pass  # fall back to a stale cached rate if we have one
    if row is None:
        return None
    return FxQuote(currency, Decimal(row.rate), row.rate_date, row.fetched_at,
                   stale=utcnow() - row.fetched_at > ttl)


class PriceDisplay:
    """Per-request helper exposed to templates as `money`."""

    def __init__(self):
        cfg = current_app.config
        self.base = cfg["BASE_CURRENCY"]
        wanted = session.get("currency", self.base)
        if wanted not in cfg["DISPLAY_CURRENCIES"]:
            wanted = self.base
        self.requested = wanted
        self.quote = get_quote(wanted) if wanted != self.base else None
        # Graceful fallback: show base currency when no rate is available
        self.currency = wanted if (wanted == self.base or self.quote) else self.base
        self.fallback = wanted != self.currency

    @property
    def converted(self):
        return self.currency != self.base

    def __call__(self, minor):
        if minor is None:
            return ""
        if self.converted:
            return "≈ " + fmt(convert(minor, self.quote.rate, self.currency), self.currency)
        return fmt_minor(minor, self.base)

    def base_fmt(self, minor):
        return fmt_minor(minor, self.base)
