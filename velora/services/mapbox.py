"""Mapbox Geocoding (https://docs.mapbox.com/api/search/geocoding/): address suggestions while typing.

The browser never talks to Mapbox and never sees the token. It calls this server's /address-search, which asks
Mapbox and returns only the few fields the address form needs. If there is no token (or Mapbox is down) the address
form simply works by hand, as before.
"""
import re
import time

import requests
from flask import current_app

from ..models import get_setting
from . import api_health


class MapboxError(Exception):
    """A problem worth showing to staff or logging."""


def token():
    """Token from the environment (.env) first, otherwise the one saved in Admin -> API health."""
    return (current_app.config.get("MAPBOX_TOKEN") or get_setting("mapbox_token") or "").strip()


def valid_token_shape(value):
    return bool(re.fullmatch(r"[ps]k\.[A-Za-z0-9._-]{20,400}", value or ""))


def _text(value, limit=200):
    return re.sub(r"\s+", " ", value).strip()[:limit] if isinstance(value, str) else ""


def _ctx(ctx, name):
    item = ctx.get(name) if isinstance(ctx, dict) else None
    return _text(item.get("name")) if isinstance(item, dict) else ""


def parse_feature(raw):
    """One Geocoding v6 feature -> the fields of our address form. None if unusable."""
    if not isinstance(raw, dict):
        return None
    props = raw.get("properties") if isinstance(raw.get("properties"), dict) else {}
    ctx = props.get("context") if isinstance(props.get("context"), dict) else {}
    coords = (raw.get("geometry") or {}).get("coordinates") if isinstance(raw.get("geometry"), dict) else None
    label = _text(props.get("full_address")) or ", ".join(x for x in (_text(props.get("name")), _text(props.get("place_formatted"))) if x)
    line1 = _ctx(ctx, "address") or _ctx(ctx, "street") or _text(props.get("name"))
    if not label or not line1:
        return None
    city = _ctx(ctx, "place") or _ctx(ctx, "locality") or _ctx(ctx, "district")
    try:
        lng, lat = float(coords[0]), float(coords[1])
    except (TypeError, ValueError, IndexError, KeyError):
        lng = lat = None
    return {"label": label, "line1": line1, "line2": _ctx(ctx, "neighborhood"), "city": city,
            "region": _ctx(ctx, "region"), "postal_code": _ctx(ctx, "postcode"),
            "country": _ctx(ctx, "country"), "lat": lat, "lng": lng}


def _call(path, params, key=None):
    """GET one Mapbox Geocoding endpoint; returns the list of parsed addresses."""
    key = key or token()  # `key` lets a not-yet-saved token be tested first
    if not key:
        raise MapboxError("Add your Mapbox token to turn on address suggestions.")
    cfg = current_app.config
    started = time.monotonic()
    try:
        resp = requests.get(cfg["MAPBOX_BASE_URL"].rstrip("/") + path, params={**params, "access_token": key},
                            timeout=cfg["HTTP_TIMEOUT"], headers={"User-Agent": api_health.user_agent(), "Accept": "application/json"})
        if resp.status_code in (401, 403):
            raise MapboxError("Mapbox didn't accept that token. Copy it again from account.mapbox.com (it starts with pk.).")
        if resp.status_code == 429:
            raise MapboxError("Mapbox's request limit was reached. Please try again in a little while.")
        resp.raise_for_status()
        data = resp.json()
    except MapboxError as exc:
        api_health.record_error(api_health.MAPBOX, str(exc))
        raise
    except (requests.RequestException, ValueError) as exc:
        api_health.record_error(api_health.MAPBOX, f"{type(exc).__name__}: {exc}")
        raise MapboxError("Couldn't reach Mapbox. You can still type the address by hand.") from exc
    api_health.record_success(api_health.MAPBOX, int((time.monotonic() - started) * 1000))
    features = data.get("features") if isinstance(data, dict) else None
    return [r for r in (parse_feature(f) for f in (features or [])) if r]


def search(query, limit=5, key=None):
    """Address suggestions for what has been typed so far. Returns a list of dicts (see parse_feature)."""
    query = _text(query, 120)
    if len(query) < 3:
        return []
    params = {"q": query, "limit": min(max(1, int(limit)), 10), "autocomplete": "true",
              "types": "address,street,neighborhood,locality,place", "language": "en"}
    if current_app.config.get("MAPBOX_COUNTRY"):
        params["country"] = current_app.config["MAPBOX_COUNTRY"]
    return _call("/search/geocode/v6/forward", params, key)


def reverse(lat, lng):
    """The address at a pinned spot (None if Mapbox knows nothing there)."""
    lat, lng = float(lat), float(lng)
    if not (-90 <= lat <= 90 and -180 <= lng <= 180):
        raise ValueError("coordinates out of range")
    found = _call("/search/geocode/v6/reverse", {"latitude": lat, "longitude": lng, "limit": 1,
                                                 "types": "address,street,neighborhood,locality,place", "language": "en"})
    return found[0] if found else None
