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
    "shoes": "shoes fashion",
    "accessories": "fashion accessories",
    "gifts-gourmet": "luxury gift box",
}


# What Find photos searches for, per product (by product slug): specific, so the right item shows up
PRODUCT_PHOTO_QUERIES = {
    "linen-wrap-midi-dress": "woman wearing linen wrap dress",
    "red-silk-slip-dress": "woman red silk slip dress",
    "cropped-leather-biker-jacket": "woman leather biker jacket",
    "relaxed-straight-jeans": "woman straight leg jeans",
    "tailored-wool-suit": "man tailored suit",
    "heavyweight-white-tee": "man white t-shirt",
    "utility-field-jacket": "man field jacket outdoors",
    "red-runner-sneakers": "red running sneakers",
    "white-leather-court-sneakers": "white leather sneakers",
    "suede-chelsea-boots": "suede chelsea boots",
    "classic-leather-loafers": "leather loafers",
    "block-heel-leather-sandals": "block heel sandals",
    "tortoiseshell-sunglasses": "tortoiseshell sunglasses",
    "aviator-sunglasses": "aviator sunglasses",
    "italian-leather-belt": "leather belt",
    "printed-silk-scarf": "silk scarf",
    "leather-card-holder": "leather card holder wallet",
    "minimalist-leather-strap-watch": "minimalist leather strap watch",
    "chronograph-steel-watch": "chronograph steel watch",
    "classic-gold-tone-dress-watch": "gold dress watch",
    "diver-automatic-200m": "diver watch",
    "smart-fitness-watch": "smartwatch fitness",
    "18k-gold-stacking-rings-set-of-3": "gold stacking rings",
    "freshwater-pearl-drop-earrings": "pearl drop earrings",
    "diamond-solitaire-pendant": "diamond pendant necklace",
    "sterling-silver-chain-bracelet": "silver chain bracelet",
    "signature-jewelry-gift-set": "jewelry gift box",
    "structured-leather-tote": "leather tote bag",
    "quilted-chain-crossbody": "quilted chain crossbody bag",
    "everyday-canvas-backpack": "canvas backpack",
    "evening-leather-clutch": "leather clutch bag",
    "weekender-duffel-bag": "weekender duffel bag",
    "luxury-gift-box": "luxury gift box ribbon",
    "72-dark-chocolate-bar": "dark chocolate bar",
    "single-origin-coffee-beans": "coffee beans bag",
    "scented-soy-candle": "scented candle",
}


def product_query(product):
    """The best first search for a product: its own specific query, else one for its collection."""
    return PRODUCT_PHOTO_QUERIES.get(product.slug) or PRODUCT_QUERIES.get(product.category.slug) or product.name


def setting_key(slot):
    return f"photo_{slot}"


def credit_key(slot):
    return f"photo_{slot}_credit"
