"""Find out which product photos actually load, so missing or broken ones can be replaced."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests
from flask import current_app

from . import api_health


def remote_ok(url, timeout=6, user_agent="VeloraMarket/1.0"):
    """True if the URL answers with an image. (Runs in worker threads, so it must not touch the Flask app.)"""
    try:
        resp = requests.get(url, stream=True, timeout=timeout, headers={"User-Agent": user_agent})
        try:
            return resp.status_code == 200 and resp.headers.get("Content-Type", "").lower().startswith("image/")
        finally:
            resp.close()
    except requests.RequestException:
        return False


def check_remote(urls, workers=8):
    """{url: works?} for many URLs at once."""
    urls = sorted({u for u in urls if u and u.startswith(("http://", "https://"))})
    if not urls:
        return {}
    agent = api_health.user_agent()  # read here, in the request thread: worker threads have no app context
    with ThreadPoolExecutor(max_workers=workers) as pool:
        return dict(zip(urls, pool.map(lambda u: remote_ok(u, user_agent=agent), urls)))


def local_ok(filename):
    return bool(filename) and (Path(current_app.config["UPLOAD_FOLDER"]) / filename).is_file()


def static_ok(url):
    """Photos that ship with the store, e.g. /static/img/watches/navy-diver-rubber.webp."""
    if not (url or "").startswith("/static/"):
        return False
    root = Path(current_app.static_folder).resolve()
    path = (root / url[len("/static/"):]).resolve()
    return path.is_relative_to(root) and path.is_file()


def working_images(product, remote_status):
    """The product's images that really load (local files that exist, remote links that answer)."""
    return [img for img in product.images
            if (img.filename and local_ok(img.filename)) or (img.url and (static_ok(img.url) or remote_status.get(img.url)))]
