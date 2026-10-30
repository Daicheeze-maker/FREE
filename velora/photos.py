"""Site photo slots (hero, banners, sign-in art). Staff can replace any slot with their own
model photos from Seller studio → Model photos, or in bulk with `flask --app wsgi load-model-photos`."""


def U(photo_id, w=1100):
    return f"https://images.unsplash.com/photo-{photo_id}?w={w}&q=80&auto=format&fit=crop"


# key: (label, where it appears, default image)
SLOTS = {
    "hero": ("Homepage hero", "Large model photo at the top of the homepage", U("1529139574466-a303027c1d8b")),
    "lookbook": ("Lookbook tile", "“Worn by our team” tile beside the collections panel", U("1483985988355-763728e1935b", 800)),
    "promo": ("Sale banner", "Big promotional tile on the homepage", U("1490481651871-ab68de25d43d")),
    "login": ("Sign-in page", "Photo on the sign-in screen", U("1469334031218-e382a71b716b")),
    "register": ("Create-account page", "Photo on the registration screen", U("1539109136881-3be0616acf4b")),
}


def setting_key(slot):
    return f"photo_{slot}"
