"""Pexels integration (https://www.pexels.com/api/): free professional photos for the storefront.

Used from Seller studio -> Find photos. A staff member searches, previews and picks a photo; the server
re-fetches that photo from Pexels by id (browser-supplied URLs are never trusted), downloads it, re-encodes
it and stores it locally, so the site keeps working even if Pexels is unreachable later.
"""
import re
import time
from dataclasses import dataclass
from urllib.parse import urlparse

import requests
from flask import current_app

from ..models import get_setting
from . import api_health


class PexelsError(Exception):
    """A problem worth showing to the person using Find photos."""


class PexelsNotConfigured(PexelsError):
    pass


@dataclass
class PexelsPhoto:
    id: int
    alt: str
    photographer: str
    page_url: str
    thumb: str      # small preview shown in the picker
    image: str      # the 800x1200 portrait crop that gets downloaded
    width: int
    height: int

    @property
    def credit(self):
        return f"Photo by {self.photographer} on Pexels"[:200]


def api_key():
    """Key from the environment (.env) first, otherwise the one a staff member saved in Find photos."""
    return (current_app.config.get("PEXELS_API_KEY") or get_setting("pexels_api_key") or "").strip()


def _clean(value, limit):
    return re.sub(r"\s+", " ", value).strip()[:limit] if isinstance(value, str) else ""


def image_url_ok(url):
    """Only images from Pexels' own image host may be shown or downloaded (also blocks SSRF tricks)."""
    if not isinstance(url, str) or len(url) > 600:
        return False
    parts = urlparse(url)
    host = parts.hostname or ""
    cfg = current_app.config
    if host not in cfg["PEXELS_IMAGE_HOSTS"]:
        return False
    return parts.scheme == "https" or (parts.scheme == "http" and host in cfg["PEXELS_ALLOW_HTTP_HOSTS"])


def parse_photo(raw):
    """Validate and normalise one photo object from the API. Returns None for anything unusable."""
    if not isinstance(raw, dict):
        return None
    src = raw.get("src") if isinstance(raw.get("src"), dict) else {}
    image = src.get("portrait") or src.get("large") or src.get("original")
    thumb = src.get("medium") or src.get("small") or image
    try:
        pid, width, height = int(raw["id"]), int(raw.get("width") or 0), int(raw.get("height") or 0)
    except (KeyError, TypeError, ValueError):
        return None
    if not (image_url_ok(image) and image_url_ok(thumb)):
        return None
    page_url = raw.get("url") if isinstance(raw.get("url"), str) and raw["url"].startswith("https://www.pexels.com/") else ""
    return PexelsPhoto(id=pid, alt=_clean(raw.get("alt"), 200) or "Fashion photo",
                       photographer=_clean(raw.get("photographer"), 80) or "a Pexels photographer",
                       page_url=page_url, thumb=thumb, image=image, width=width, height=height)


def _get(path, params=None, key=None):
    key = key or api_key()  # `key` lets a new, not-yet-saved key be tested without storing it first
    if not key:
        raise PexelsNotConfigured("Add your free Pexels key to search for photos.")
    cfg = current_app.config
    started = time.monotonic()
    try:
        resp = requests.get(cfg["PEXELS_BASE_URL"].rstrip("/") + path, params=params, timeout=cfg["HTTP_TIMEOUT"],
                            headers={"Authorization": key, "User-Agent": api_health.user_agent(), "Accept": "application/json"})
        if resp.status_code in (401, 403):
            raise PexelsError("Pexels didn't accept that key. Copy it again from pexels.com/api (it's one long line).")
        if resp.status_code == 429:
            raise PexelsError("Pexels' free limit is 200 searches an hour. Please wait a little and try again.")
        resp.raise_for_status()
        data = resp.json()
    except PexelsError as exc:
        api_health.record_error(api_health.PEXELS, str(exc))
        raise
    except (requests.RequestException, ValueError) as exc:
        api_health.record_error(api_health.PEXELS, f"{type(exc).__name__}: {exc}")
        raise PexelsError("Couldn't reach Pexels. Check your internet connection and try again. "
                          "Everything already on the site keeps working.") from exc
    api_health.record_success(api_health.PEXELS, int((time.monotonic() - started) * 1000))
    return data


def search(query, page=1, per_page=18, orientation="portrait", key=None):
    """Returns (photos, total_results)."""
    query = _clean(query, 100)
    if len(query) < 2:
        return [], 0
    data = _get("/search", {"query": query, "page": max(1, int(page)), "per_page": min(max(1, int(per_page)), 40),
                            "orientation": orientation}, key=key)
    raw = data.get("photos") if isinstance(data, dict) else None
    photos = [p for p in (parse_photo(r) for r in (raw or [])) if p]
    try:
        total = int(data.get("total_results") or len(photos))
    except (TypeError, ValueError, AttributeError):
        total = len(photos)
    return photos, total


def get_photo(photo_id):
    photo = parse_photo(_get(f"/photos/{int(photo_id)}"))
    if photo is None:
        raise PexelsError("Pexels returned a photo we can't use. Please pick another.")
    return photo


def download(photo):
    """Fetch the photo's bytes (size-capped, Pexels image host only)."""
    if not image_url_ok(photo.image):
        raise PexelsError("That photo isn't hosted by Pexels, so it was not downloaded.")
    cfg = current_app.config
    limit = cfg["PHOTO_DOWNLOAD_MAX_MB"] * 1024 * 1024
    try:
        resp = requests.get(photo.image, timeout=cfg["HTTP_TIMEOUT"] * 2, stream=True, allow_redirects=False,
                            headers={"User-Agent": api_health.user_agent()})
        resp.raise_for_status()
        chunks, size = [], 0
        for chunk in resp.iter_content(64 * 1024):
            size += len(chunk)
            if size > limit:
                raise PexelsError("That photo is too large to download.")
            chunks.append(chunk)
    except PexelsError:
        raise
    except requests.RequestException as exc:
        raise PexelsError("The photo couldn't be downloaded. Please try again.") from exc
    return b"".join(chunks)
