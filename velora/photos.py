"""Site photo slots (hero, banners, sign-in art).

Until a photo is chosen a slot shows a neutral placeholder. Staff fill them in Seller studio -> Model photos:
upload your own, or use Find photos to pick professional photos from Pexels (free).
"""

# key: (label, where it appears, search used by Find photos / auto-fill)
SLOTS = {
    "hero": ("Homepage hero", "Large model photo at the top of the homepage", "fashion model portrait studio"),
    "lookbook": ("Lookbook tile", "Photo beside the collections panel", "fashion editorial model standing"),
    "promo": ("Sale banner", "Big promotional tile on the homepage", "woman fashion model dress outdoor"),
    "login": ("Sign-in page", "Photo on the sign-in screen", "fashion model street style"),
    "register": ("Create-account page", "Photo on the registration screen", "stylish model portrait"),
}

# What Find photos searches for when opened from a product (by collection slug)
PRODUCT_QUERIES = {
    "women": "woman fashion model wearing dress",
    "men": "man fashion model jacket",
    "watches": "wristwatch on wrist model",
    "jewelry": "model wearing jewelry necklace",
    "bags": "woman with handbag fashion",
    "gifts-gourmet": "luxury gift box",
}


def setting_key(slot):
    return f"photo_{slot}"


def credit_key(slot):
    return f"photo_{slot}_credit"
