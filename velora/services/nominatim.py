"""OpenStreetMap Nominatim reverse geocoding (https://nominatim.org/release-docs/latest/api/Reverse/).

Free, no key. Used to turn a pin on the map into an address when no Mapbox token is set (or Mapbox is down),
so "pin my location" always fills in the address form. One request per pin drop, as the usage policy asks.
"""
import re
import time

import requests
from flask import current_app

from . import api_health
from .mapbox import MapboxError


def _t(v, n=200):
    return re.sub(r"\s+", " ", v).strip()[:n] if isinstance(v, str) else ""


def parse(data):
    addr = data.get("address") if isinstance(data, dict) and isinstance(data.get("address"), dict) else None
    if not addr:
        return None
    street = _t(addr.get("road") or addr.get("pedestrian") or addr.get("footway") or addr.get("neighbourhood") or addr.get("suburb"))
    if not street:
        return None
    number = _t(addr.get("house_number"), 30)
    city = _t(addr.get("city") or addr.get("town") or addr.get("municipality") or addr.get("village") or addr.get("city_district") or addr.get("county"))
    region = _t(addr.get("state") or addr.get("region") or addr.get("province") or addr.get("state_district"))
    try:
        lat, lng = float(data["lat"]), float(data["lon"])
    except (KeyError, TypeError, ValueError):
        lat = lng = None
    return {"label": _t(data.get("display_name")) or street, "line1": f"{number} {street}".strip(), "line2": "",
            "city": city, "region": region, "postal_code": _t(addr.get("postcode"), 20),
            "country": _t(addr.get("country"), 60), "lat": lat, "lng": lng}


def reverse(lat, lng):
    lat, lng = float(lat), float(lng)
    if not (-90 <= lat <= 90 and -180 <= lng <= 180):
        raise ValueError("coordinates out of range")
    cfg = current_app.config
    started = time.monotonic()
    try:
        resp = requests.get(cfg["NOMINATIM_BASE_URL"].rstrip("/") + "/reverse", timeout=cfg["HTTP_TIMEOUT"],
                            params={"format": "jsonv2", "lat": lat, "lon": lng, "zoom": 18, "addressdetails": 1, "accept-language": "en"},
                            headers={"User-Agent": api_health.user_agent(), "Accept": "application/json"})
        resp.raise_for_status()
        data = resp.json()
    except (requests.RequestException, ValueError) as exc:
        api_health.record_error("nominatim", f"{type(exc).__name__}: {exc}")
        raise MapboxError("Couldn't look up that spot.") from exc
    api_health.record_success("nominatim", int((time.monotonic() - started) * 1000))
    return parse(data)
