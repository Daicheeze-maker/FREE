"""360° views: turn a watch by dragging it.

Frames live in ``velora/static/img/spin/<product-slug>/<colour>/01.webp, 02.webp, …`` (one folder per colour, in turning
order). A colour's main photo is the product image whose file name ends in ``-<colour>.webp``. Adding a 360° view to
another watch only needs its frames dropped into a folder like that; nothing else to configure.
"""
from pathlib import Path

from flask import current_app

from .services.catalog import slugify


# Watches whose 360° frames were cut from small thumbnails: shown a bit smaller so they don't look blurry
SOFT_FRAMES = set()


def spin_data(product):
    """{"colours": {name: {"main": url | None, "frames": [url, …]}}, "order": [names]} or None if the watch has no 360° view."""
    root = Path(current_app.static_folder) / "img" / "spin" / product.slug
    if not root.is_dir():
        return None
    names = product.color_list or sorted(p.name.title() for p in root.iterdir() if p.is_dir())
    colours, order = {}, []
    for name in names:
        folder = root / slugify(name)
        frames = sorted(folder.glob("*.webp")) if folder.is_dir() else []
        if len(frames) < 2:
            continue
        main = next((img.url for img in product.images if (img.url or "").endswith(f"-{slugify(name)}.webp")), None)
        base = f"{current_app.static_url_path}/img/spin/{product.slug}/{slugify(name)}"
        colours[name] = {"main": main, "frames": [f"{base}/{f.name}" for f in frames]}
        order.append(name)
    return {"colours": colours, "order": order, "soft": product.slug in SOFT_FRAMES} if colours else None
