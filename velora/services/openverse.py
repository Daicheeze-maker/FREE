"""Openverse (https://api.openverse.org): free, openly licensed photos, NO account or key needed.

Used as the automatic fallback when no Pexels key has been added, so product photos can still be filled in.
Photos are fetched through Openverse's own thumbnail endpoint (api.openverse.org only), never from arbitrary hosts,
then re-encoded and stored locally like any other photo. The licence credit is saved with the photo.
"""
import re
import time
from urllib.parse import urlparse

import requests
from flask import current_app

from . import api_health
from .pexels import PexelsError, PexelsPhoto, _clean

NAME = "Openverse"
UUID = re.compile(r"^[0-9a-f-]{32,40}$")


def _licence(raw):
    lic = _clean(raw.get("license"), 20).upper()
    ver = _clean(raw.get("license_version"), 10)
    return f"CC {lic}{' ' + ver if ver else ''}" if lic and lic not in ("CC0", "PDM") else (lic or "open licence")


def parse(raw, base):
    if not isinstance(raw, dict):
        return None
    pid = raw.get("id")
    if not isinstance(pid, str) or not UUID.match(pid):
        return None
    try:
        width, height = int(raw.get("width") or 0), int(raw.get("height") or 0)
    except (TypeError, ValueError):
        return None
    creator = _clean(raw.get("creator"), 60) or "an unknown photographer"
    title = _clean(raw.get("title"), 80) or "Photo"
    thumb = f"{base}/v1/images/{pid}/thumb/"
    landing = raw.get("foreign_landing_url") if isinstance(raw.get("foreign_landing_url"), str) and raw["foreign_landing_url"].startswith("https://") else ""
    return PexelsPhoto(id=pid, alt=title, photographer=creator, page_url=landing, thumb=thumb, image=thumb,
                       width=width, height=height)


def credit(photo, licence):
    return f"“{photo.alt}” by {photo.photographer} ({licence}) via Openverse"[:200]


def search(query, page=1, per_page=15):
    """Returns (photos, total). Each photo has .credit text with its licence."""
    query = _clean(query, 100)
    if len(query) < 2:
        return [], 0
    cfg = current_app.config
    base = cfg["OPENVERSE_BASE_URL"].rstrip("/")
    started = time.monotonic()
    try:
        resp = requests.get(base + "/v1/images/", timeout=cfg["HTTP_TIMEOUT"],
                            params={"q": query, "page": max(1, int(page)), "page_size": min(per_page, 20), "license_type": "commercial",
                                    "mature": "false", "aspect_ratio": "tall", "category": "photograph"},
                            headers={"User-Agent": api_health.user_agent(), "Accept": "application/json"})
        if resp.status_code in (401, 403, 429):
            raise PexelsError("The free photo source is busy right now. Please try again in a few minutes.")
        resp.raise_for_status()
        data = resp.json()
    except PexelsError:
        raise
    except (requests.RequestException, ValueError) as exc:
        api_health.record_error("openverse", f"{type(exc).__name__}: {exc}")
        raise PexelsError("Couldn't reach the free photo source. Check your internet connection and try again.") from exc
    api_health.record_success("openverse", int((time.monotonic() - started) * 1000))
    photos = []
    for raw in (data.get("results") if isinstance(data, dict) else None) or []:
        p = parse(raw, base)
        if p is not None:
            p.credit_text = credit(p, _licence(raw))
            photos.append(p)
    return photos, int(data.get("result_count") or len(photos)) if isinstance(data, dict) else len(photos)


def download(photo):
    """Fetch the photo's bytes (api.openverse.org only, size-capped)."""
    cfg = current_app.config
    base_host = urlparse(cfg["OPENVERSE_BASE_URL"]).hostname
    if urlparse(photo.image).hostname != base_host:
        raise PexelsError("That photo isn't from the photo source, so it was not downloaded.")
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
