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
    "hero": "luna-blue-moonphase-40-blue",
    "lookbook": "abyss-300-black-black",
    "promo": "panda-racing-42-white",
    "login": "riviera-blue-chrono-41-blue",
    "register": "trail-field-40-black",
}

# ...and if that file is missing, the photo of one of these watches (first one that has a photo)
DEFAULT_SLOT_PRODUCTS = {
    "hero": ("luna-blue-moonphase-40", "panda-racing-42"),
    "lookbook": ("abyss-300-black", "sottile-ultra-thin-38"),
    "promo": ("panda-racing-42", "riviera-blue-chrono-41"),
    "login": ("riviera-blue-chrono-41", "abyss-300-black"),
    "register": ("trail-field-40", "scout-field-39"),
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
PRODUCT_PHOTO_QUERIES = {}


def product_query(product):
    """The best first search for a product: its own specific query, else one for its collection."""
    return PRODUCT_PHOTO_QUERIES.get(product.slug) or PRODUCT_QUERIES.get(product.category.slug) or f"{product.name} watch"


def setting_key(slot):
    return f"photo_{slot}"


def credit_key(slot):
    return f"photo_{slot}_credit"
