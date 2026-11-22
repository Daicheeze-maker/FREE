"""Site photo slots (hero, banners, sign-in art) and the searches used to find watch photos.

Until a photo is chosen a slot shows the photo of one of the watches. Staff change them in Seller studio -> Site photos:
upload your own, or use Find photos (Pexels, free).
"""

# key: (label, where it appears, search used by Find photos / auto-fill)
SLOTS = {
    "hero": ("Homepage hero", "Large photo at the top of the homepage", "wristwatch on wrist close up"),
    "lookbook": ("Collections tile", "Photo beside the collections panel", "luxury watches display"),
    "promo": ("Sale banner", "Big promotional tile on the homepage", "watch on wrist outdoor"),
    "login": ("Sign-in page", "Photo on the sign-in screen", "classic wristwatch"),
    "register": ("Create-account page", "Photo on the registration screen", "automatic watch dial"),
}

# Until staff choose a photo, each slot shows one of the store's own photos (velora/static/img/watches/)
DEFAULT_SLOT_FILES = {
    "hero": "blue-skeleton-wrist",
    "lookbook": "watch-collection-gloves",
    "promo": "panda-chrono-wrist",
    "login": "navy-diver-rubber",
    "register": "green-field-leather-rope",
}

# ...and if that file is missing, the photo of one of these watches (first one that has a photo)
DEFAULT_SLOT_PRODUCTS = {
    "hero": ("minimalist-leather-strap-watch", "chronograph-steel-watch", "diver-automatic-200m"),
    "lookbook": ("classic-gold-tone-dress-watch", "diver-automatic-200m", "minimalist-leather-strap-watch"),
    "promo": ("chronograph-steel-watch", "smart-fitness-watch", "minimalist-leather-strap-watch"),
    "login": ("diver-automatic-200m", "classic-gold-tone-dress-watch", "minimalist-leather-strap-watch"),
    "register": ("minimalist-leather-strap-watch", "smart-fitness-watch", "chronograph-steel-watch"),
}

# What Find photos searches for when opened from a product (by collection slug)
PRODUCT_QUERIES = {
    "dress-watches": "dress wristwatch leather strap",
    "dive-watches": "diver watch wrist",
    "chronographs": "chronograph wristwatch",
    "field-pilot": "field watch canvas strap",
    "smart-watches": "smartwatch on wrist",
    "ladies-watches": "women rose gold wristwatch",
}

# What Find photos searches for, per watch (by product slug): specific, so the right watch shows up
PRODUCT_PHOTO_QUERIES = {
    "minimalist-leather-strap-watch": "minimalist wristwatch leather strap",
    "classic-gold-tone-dress-watch": "gold dress watch",
    "moonphase-automatic-dress-watch": "moonphase watch",
    "slim-skeleton-watch": "skeleton watch",
    "diver-automatic-200m": "automatic dive watch",
    "deep-blue-titanium-diver": "blue dial dive watch",
    "pro-dive-rubber-strap-watch": "dive watch rubber strap",
    "chronograph-steel-watch": "steel chronograph watch",
    "racing-chronograph-leather": "racing chronograph watch",
    "tachymeter-sport-chrono": "tachymeter watch",
    "field-automatic-watch": "field watch",
    "pilot-aviator-watch": "pilot watch",
    "explorer-canvas-strap-watch": "explorer watch canvas strap",
    "smart-fitness-watch": "fitness smartwatch",
    "smart-hybrid-watch": "hybrid smartwatch",
    "smart-gps-sport-watch": "gps sport watch",
    "rose-gold-bracelet-watch": "rose gold bracelet watch",
    "pearl-dial-ladies-watch": "pearl dial watch women",
    "petite-mesh-watch": "mesh strap watch women",
    "spectrum-chronograph": "colorful rubber strap chronograph watch",
}


def product_query(product):
    """The best first search for a product: its own specific query, else one for its collection."""
    return PRODUCT_PHOTO_QUERIES.get(product.slug) or PRODUCT_QUERIES.get(product.category.slug) or f"{product.name} watch"


def setting_key(slot):
    return f"photo_{slot}"


def credit_key(slot):
    return f"photo_{slot}_credit"
