"""Repeatable demo data: a watch store. Safe to run more than once: it only seeds an empty database.

Photos are hot-linked from Unsplash (free to use under the Unsplash License). Every watch lists a few candidate photos:
the first is stored, and the browser moves on to the next one by itself if a photo has gone from Unsplash.
If none loads, the storefront swaps in a local placeholder. `fill-photos` can replace any of them.
"""
import random
import secrets
from datetime import timedelta

from .extensions import db
from .models import (DEFAULT_SETTINGS, SELLER_SUFFIX, STARTING_CREDIT_MINOR, Address, Cart, CartItem, Category, DiscountCode, Notification, Order,
                     OrderItem, OrderStatus, PaymentRecord, Product, ProductImage, ProductReview, StoreSetting, User,
                     WishlistItem, utcnow)
from .services.catalog import slugify


def U(photo_id, w=900):
    return f"https://images.unsplash.com/photo-{photo_id}?w={w}&q=80&auto=format&fit=crop"


CATEGORIES = [
    ("Dress Watches", "watch", "Slim, polished watches for work, weddings and big nights."),
    ("Dive Watches", "waves", "Water-resistant automatics built for the sea and the city."),
    ("Chronographs", "timer", "Stopwatch subdials, tachymeters and racing style."),
    ("Field & Pilot", "compass", "Rugged, legible watches on canvas, leather or steel."),
    ("Smart Watches", "smartphone", "Fitness, GPS and hybrid watches that do more than tell time."),
    ("Ladies Watches", "gem", "Rose gold, pearl and crystal watches in smaller case sizes."),
]

# Verified-working photos (they loaded on real screens) end each chain, so every watch always ends on a real watch photo.
V1, V2, V3, V4, V5 = ("1523275335684-37898b6baf30", "1522312346375-d1a52e2b99b3", "1524592094714-0f0654e20314",
                      "1547996160-81dfa63595aa", "1434056886845-dac89ffe9b56")

DRESS_COLORS, SPORT_COLORS, SMART_COLORS = "Silver,Gold,Rose Gold", "Black,Blue,Green", "Midnight,Starlight,Rose Gold"
STRAP_COLORS = "Black,Brown,Tan"

# (name, brand, category idx, price ₱, compare_at, stock, note, origin, featured, sold, photo ids (first one is stored),
#  short description, description, specs, case sizes, colours, engraving fee ₱ or None)
PRODUCTS = [
    ("Minimalist Leather Strap Watch", "Horloge & Co", 0, 6990, None, 24, "Quartz · 3 ATM", "Swiss movement", True, 260,
     [V1], "Clean dial · genuine leather strap",
     "An everyday dress watch with a clean, uncluttered dial, slim case and a genuine leather strap that softens with wear.",
     "Stainless steel case, sapphire-coated glass, leather strap, Swiss quartz movement.", "36 mm,40 mm", DRESS_COLORS, 500),
    ("Classic Gold-Tone Dress Watch", "Maison Lune", 0, 8490, 9990, 15, "Quartz · 3 ATM", "Swiss movement", True, 190,
     [V3], "Slim case · gold-tone finish",
     "A slim gold-tone dress watch that slides under a shirt cuff, made for weddings and big nights.",
     "Gold-tone steel case, mineral crystal, calfskin strap.", "34 mm,38 mm", "Gold,Rose Gold,Silver", 500),
    ("Moonphase Automatic Dress Watch", "Horloge & Co", 0, 24900, 28900, 3, "Automatic · 5 ATM", "Swiss movement", False, 64,
     ["1508685096489-7aacd43bd3b1", "1524805444758-089113d48a6d", V3], "Moonphase subdial · automatic",
     "A self-winding dress watch with a moonphase subdial and exhibition case back, finished by hand.",
     "Stainless steel, sapphire crystal, automatic movement with 40 h power reserve.", "39 mm,42 mm", "Silver,Gold,Black", 800),
    ("Slim Skeleton Watch", "Maison Lune", 0, 18500, None, 6, "Manual wind · 3 ATM", "Swiss movement", False, 41,
     ["1587836374828-4dbafa94cf0e", "1542496658-e33a6d0d50f6", V1], "Open-worked dial · see the movement",
     "An open-worked dial that shows the movement at work, on a slim case and a hand-stitched strap.",
     "Stainless steel, sapphire crystal, hand-wound skeleton movement.", "38 mm,41 mm", "Silver,Gold,Rose Gold", 800),

    ("Diver Automatic 200m", "Tidewater", 1, 14990, None, 18, "Automatic · 200 m", "Japan movement", True, 210,
     [V4], "200 m water resistant · luminous dial",
     "A proper dive watch: screw-down crown, unidirectional bezel and a luminous dial you can read in the dark.",
     "Stainless steel case, sapphire crystal, automatic movement, rubber or steel strap.", "40 mm,42 mm,44 mm", SPORT_COLORS, 600),
    ("Deep Blue Titanium Diver", "Tidewater", 1, 32500, 36900, 7, "Automatic · 300 m", "Swiss movement", False, 52,
     ["1539874754764-5a96559165b0", "1612817159949-195b6eb9e31a", V4], "Titanium case · 300 m",
     "A light, hard-wearing titanium diver rated to 300 m with a ceramic bezel and a helium escape valve.",
     "Grade 2 titanium, ceramic bezel, sapphire crystal, automatic movement.", "42 mm,44 mm", "Blue,Black,Grey", 800),
    ("Pro Dive Rubber Strap Watch", "Tidewater", 1, 9990, None, 22, "Quartz · 200 m", "Japan movement", False, 138,
     ["1619134778706-7015533a6150", "1560343090-f0409e92791a", V4], "Quartz diver · soft rubber strap",
     "A value dive watch with a rotating bezel and a soft rubber strap that is comfortable all day, in or out of the water.",
     "Stainless steel, mineral crystal, rubber strap, quartz movement.", "40 mm,44 mm", "Black,Blue,Green", 500),

    ("Chronograph Steel Watch", "Northfield", 2, 11500, None, 20, "Quartz · 5 ATM", "Japan movement", True, 175,
     [V2], "Three subdials · steel bracelet",
     "A sporty stainless steel chronograph with three subdials, a date window and a solid link bracelet.",
     "Stainless steel case and bracelet, mineral crystal, quartz chronograph movement.", "40 mm,42 mm,44 mm", "Steel,Black,Blue", 600),
    ("Racing Chronograph Leather", "Northfield", 2, 13900, 15900, 12, "Quartz · 10 ATM", "Japan movement", False, 96,
     ["1622434641406-a158123450f9", "1585123334904-845d60e97b29", V2], "Racing dial · perforated leather strap",
     "A racing-inspired chronograph with a contrast dial and a perforated leather strap.",
     "Stainless steel, sapphire-coated glass, leather strap, quartz chronograph movement.", "42 mm,44 mm", "Black,Brown,Blue", 600),
    ("Tachymeter Sport Chrono", "Pulse", 2, 9490, None, 26, "Quartz · 10 ATM", "Japan movement", False, 112,
     ["1594534475808-b18fc33b045e", "1533139143976-30e4d0a0f6e0", V2], "Tachymeter bezel · silicone strap",
     "A lightweight sport chronograph with a tachymeter bezel and a quick-change silicone strap.",
     "Steel case, mineral crystal, silicone strap, quartz chronograph movement.", "41 mm,45 mm", "Black,Blue,Red", None),

    ("Field Automatic Watch", "Northfield", 3, 12500, None, 14, "Automatic · 10 ATM", "Japan movement", False, 77,
     ["1548171916-c8fd1c9d4e5a", "1560343090-f0409e92791a", V1], "Legible dial · canvas strap",
     "A no-nonsense field watch with a high-contrast, legible dial and a washable canvas strap.",
     "Stainless steel, hardened crystal, canvas strap, automatic movement.", "38 mm,40 mm", "Green,Black,Tan", 600),
    ("Pilot Aviator Watch", "Horloge & Co", 3, 15900, 17900, 10, "Automatic · 10 ATM", "Swiss movement", True, 88,
     ["1542496658-e33a6d0d50f6", "1587836374828-4dbafa94cf0e", V2], "Large crown · big numerals",
     "An aviator-style watch with big numerals, an oversize crown that works with gloves and a soft leather strap.",
     "Stainless steel, sapphire crystal, leather strap, automatic movement.", "40 mm,43 mm", "Black,Brown,Blue", 700),
    ("Explorer Canvas Strap Watch", "Pulse", 3, 7990, None, 28, "Quartz · 10 ATM", "Japan movement", False, 143,
     ["1585123334904-845d60e97b29", "1508685096489-7aacd43bd3b1", V1], "Date window · luminous hands",
     "A hard-wearing everyday explorer with a date window, luminous hands and a canvas strap.",
     "Stainless steel, mineral crystal, canvas strap, quartz movement.", "38 mm,42 mm", "Green,Tan,Black", 500),

    ("Smart Fitness Watch", "Pulse", 4, 8990, None, 40, "Heart rate · GPS · 5 ATM", "Imported", True, 305,
     [V5], "Heart rate, sleep and workout tracking",
     "A smart fitness watch with heart-rate and sleep tracking, built-in GPS, phone notifications and a 7-day battery.",
     "Aluminium case, AMOLED display, silicone strap. Works with Android and iPhone.", "40 mm,44 mm", SMART_COLORS, 500),
    ("Smart Hybrid Watch", "Pulse", 4, 6490, None, 30, "Hybrid · 6-month battery", "Imported", False, 121,
     ["1546868871-7041f2a55e12", "1579586337278-3befd40fd17a", V5], "Analog dial · smart alerts",
     "A hybrid that looks like a classic analog watch but counts steps, tracks sleep and buzzes for calls, with a 6-month battery.",
     "Stainless steel, mineral crystal, leather strap, replaceable battery.", "38 mm,42 mm", "Black,Silver,Rose Gold", 500),
    ("Smart GPS Sport Watch", "Pulse", 4, 14990, 16990, 16, "GPS · multi-sport · 10 ATM", "Imported", False, 67,
     ["1579586337278-3befd40fd17a", "1546868871-7041f2a55e12", V5], "Multi-sport GPS · 2-week battery",
     "A rugged multi-sport GPS watch with route maps, 24 sport modes and a two-week battery.",
     "Fibre-reinforced case, sapphire glass, silicone strap.", "42 mm,47 mm", "Black,Blue,Green", None),

    ("Rose Gold Bracelet Watch", "Maison Lune", 5, 9990, 11990, 18, "Quartz · 3 ATM", "Swiss movement", True, 168,
     ["1612817159949-195b6eb9e31a", "1594534475808-b18fc33b045e", V3], "Rose gold-tone · slim bracelet",
     "A dainty rose gold-tone bracelet watch with a mother-of-pearl dial.",
     "Rose gold-tone steel, sapphire-coated glass, quartz movement.", "28 mm,32 mm", "Rose Gold,Gold,Silver", 500),
    ("Pearl Dial Ladies Watch", "Maison Lune", 5, 11900, None, 12, "Quartz · 3 ATM", "Swiss movement", False, 74,
     ["1533139143976-30e4d0a0f6e0", "1619134778706-7015533a6150", V3], "Mother-of-pearl dial · leather strap",
     "A softly glowing mother-of-pearl dial on a slim case and a soft leather strap.",
     "Stainless steel, sapphire-coated glass, leather strap.", "30 mm,34 mm", "Silver,Gold,Rose Gold", 500),
    ("Petite Mesh Watch", "Horloge & Co", 5, 5990, None, 25, "Quartz · 3 ATM", "Japan movement", False, 133,
     ["1539874754764-5a96559165b0", "1622434641406-a158123450f9", V1], "Milanese mesh · petite case",
     "A petite case on an adjustable Milanese mesh strap that fits any wrist without tools.",
     "Stainless steel case and mesh strap, mineral crystal.", "26 mm,30 mm", "Silver,Gold,Rose Gold", None),
    ("Crystal Bezel Watch", "Maison Lune", 5, 13500, 15500, 0, "Quartz · 5 ATM", "Swiss movement", False, 58,
     ["1560343090-f0409e92791a", "1508685096489-7aacd43bd3b1", V3], "Crystal-set bezel · bracelet",
     "A crystal-set bezel that catches the light, on a polished link bracelet.",
     "Stainless steel, crystals, sapphire-coated glass, quartz movement.", "30 mm,33 mm", "Silver,Gold,Rose Gold", 700),
    ("Spectrum Chronograph", "Aurelune Studio", 2, 12900, 14900, 30, "Quartz chronograph · 10 ATM", "Japan movement", True, 186,
     [V2], "Ten colour editions · drag for a 360° view",
     "A bold sport chronograph with a matte black case, three subdials and a soft rubber strap, in ten colour editions. "
     "Pick your colour and drag the photo to turn the watch all the way around.",
     "Black PVD steel case, mineral crystal, FKM rubber strap, quartz chronograph movement.", "42 mm,44 mm",
     "Black,White,Blue,Red,Green,Purple,Pink,Orange,Yellow,Teal", 500),
]

WATCH_SLUGS = {slugify(row[0]) for row in PRODUCTS}

# The store's own photos (velora/static/img/watches/), first one is the cover. They ship with the project, so they
# always load. Watches not listed here use the Unsplash photos in PRODUCTS.
OWN_PHOTOS = {
    "minimalist-leather-strap-watch": ["rose-gold-dress-black-strap"],
    "classic-gold-tone-dress-watch": ["rose-gold-dress-closeup", "rose-gold-dress-angle"],
    "slim-skeleton-watch": ["blue-skeleton-wrist", "blue-skeleton-tourbillon", "blue-skeleton-outdoor"],
    "diver-automatic-200m": ["black-dial-luminor-rock"],
    "pro-dive-rubber-strap-watch": ["navy-diver-rubber"],
    "chronograph-steel-watch": ["fluted-blue-chrono-front", "fluted-blue-chrono-side", "fluted-blue-chrono-back"],
    "racing-chronograph-leather": ["blue-steel-chrono-front", "blue-steel-chrono-side", "blue-steel-chrono-back"],
    "tachymeter-sport-chrono": ["panda-chrono-wrist", "panda-chrono-display"],
    "pilot-aviator-watch": ["black-pilot-leather"],
    "field-automatic-watch": ["green-field-leather-rope", "green-field-leather-front", "green-field-leather-side"],
    # one photo per colour edition, in the same order as its colours (the 360° frames are in static/img/spin/)
    "spectrum-chronograph": [f"spectrum-{c}" for c in ("black", "white", "blue", "red", "green", "purple", "pink",
                                                         "orange", "yellow", "teal")],
}
OWN_CREDIT = "Store photo"


def own_photo_url(name):
    return f"/static/img/watches/{name}.webp"


def apply_own_photos(product):
    """Give a watch the store's own photos in place of stand-in stock photos. Photos a seller uploaded or picked
    (saved files) are never replaced; a photo link a seller typed in is kept after the store's own. True if changed."""
    names = OWN_PHOTOS.get(product.slug)
    if not names or any(i.filename for i in product.images):
        return False
    wanted = [own_photo_url(n) for n in names]
    if [i.url for i in product.images[:len(wanted)]] == wanted:
        return False
    stand_in = lambda i: (i.credit or "") in ("Unsplash", OWN_CREDIT) or (i.url or "").startswith("/static/img/watches/")
    keep = [i for i in product.images if not stand_in(i)]
    for img in [i for i in product.images if stand_in(i)]:
        product.images.remove(img)
        db.session.delete(img)
    ordered = [ProductImage(url=u, alt=f"{product.name} — view {n + 1}", credit=OWN_CREDIT) for n, u in enumerate(wanted)] + keep
    for pos, img in enumerate(ordered):
        img.position = pos
        if img not in product.images:
            product.images.append(img)
    product.images.sort(key=lambda i: i.position)
    return True


def alt_next():
    """{photo id: URL of the next candidate}: lets the browser move on when a photo has been removed from its host."""
    out = {}
    for row in PRODUCTS:
        ids = row[10]
        for a, b in zip(ids, ids[1:]):
            out.setdefault(a, U(b))
    return out


def _make_product(i, row, category, now, rng):
    name, brand, ci, price, compare, stock, note, origin, featured, sold, photos, short, desc, specs, sizes, colors, engraving = row
    p = Product(name=name, slug=slugify(name), sku=f"VM-{1000 + i}", brand=brand, category=category,
                short_description=short, description=desc, price_minor=price * 100,
                compare_at_minor=compare * 100 if compare else None, stock=stock, size_label=note,
                origin=origin, is_featured=featured, sold_count=sold, ingredients=specs, sizes=sizes or None,
                colors=colors or None, engraving_fee_minor=engraving * 100 if engraving is not None else None,
                engraving_max=20, created_at=now - timedelta(days=60 - i * 2 if i < 18 else rng.randint(1, 12)))
    own = OWN_PHOTOS.get(slugify(name))
    if own:
        for pos, n in enumerate(own):
            p.images.append(ProductImage(url=own_photo_url(n), alt=f"{name} — view {pos + 1}", position=pos, credit=OWN_CREDIT))
        return p
    for pos, pid in enumerate(photos[:1]):
        p.images.append(ProductImage(url=U(pid), alt=f"{name} — {short}", position=pos, credit="Unsplash"))
    return p


REVIEWS = [
    (5, "Looks even better on the wrist", "The finish is lovely in person and it keeps good time. Packaging felt premium too."),
    (4, "Great watch, check the size", "Beautiful watch. I went one case size up from my old one and it was the right call."),
    (5, "Worth every peso", "Exactly as described and delivery was quick. Looks like the photos."),
    (5, "Perfect engraved gift", "Added an engraving for my dad's birthday. It arrived beautifully done and he loves it."),
    (3, "Good, not perfect", "Well made, but the dial colour is a little different from my screen. Service was great."),
    (4, "Solid repeat purchase", "Third watch from here now. Consistent and well packed every time."),
]


# Collections an earlier release sold (fashion, jewelry, bags, gifts, cars). They are removed when the store becomes a watch store.
OLD_COLLECTIONS = {"women", "men", "shoes", "accessories", "jewelry", "bags", "gifts-gourmet", "cars"}


def refresh_catalog():
    """Turn an existing store into the current watch store WITHOUT touching accounts, orders, settings or uploaded photos.

    Fashion, jewelry, bags and gift products (and their collections) are removed; order history keeps its snapshots.
    Watches get their collections, sizes, colours and engraving; missing watches and photos are added. Idempotent.
    Returns a list of human-readable changes (empty if nothing was needed).
    """
    from .services.uploads import delete_upload
    changes = []
    cats = {c.slug: c for c in Category.query.all()}
    for pos, (name, icon, desc) in enumerate(CATEGORIES):
        slug = slugify(name)
        cat = cats.get(slug)
        if cat is None:
            cat = Category(name=name, slug=slug, icon=icon, description=desc, position=pos)
            db.session.add(cat)
            cats[slug] = cat
            changes.append(f"added the {name} collection")
        else:
            cat.position, cat.icon, cat.description = pos, icon, desc
    db.session.flush()

    # Fashion, jewelry, bags and gift products go (the old "Watches" collection's own products stay)
    gone = [p for p in Product.query.all() if p.category.slug in OLD_COLLECTIONS]
    if gone:
        ids = [p.id for p in gone]
        OrderItem.query.filter(OrderItem.product_id.in_(ids)).update({OrderItem.product_id: None}, synchronize_session=False)
        CartItem.query.filter(CartItem.product_id.in_(ids)).delete(synchronize_session=False)
        WishlistItem.query.filter(WishlistItem.product_id.in_(ids)).delete(synchronize_session=False)
        for p in gone:
            for img in p.images:
                if img.filename:
                    delete_upload(img.filename)
            db.session.delete(p)
        db.session.flush()
        changes.append(f"removed {len(gone)} non-watch product(s)")

    rng, now = random.Random(7), utcnow()
    rows = {slugify(r[0]): (i, r) for i, r in enumerate(PRODUCTS)}
    existing = {p.slug: p for p in Product.query.all()}
    for slug, (i, row) in rows.items():
        category = cats[slugify(CATEGORIES[row[2]][0])]
        product = existing.get(slug)
        if product is None:
            sku_taken = Product.query.filter_by(sku=f"VM-{1000 + i}").first() is not None
            product = _make_product(i, row, category, now, rng)
            if sku_taken:
                product.sku = f"VM-{9000 + i}"
            db.session.add(product)
            changes.append(f"added {product.name}")
            continue
        if product.category_id != category.id:
            product.category = category
            changes.append(f"moved {product.name} to {category.name}")
        if product.colors is None and product.sizes is None and product.engraving_fee_minor is None:
            product.sizes, product.colors = row[14] or None, row[15] or None
            product.engraving_fee_minor = row[16] * 100 if row[16] is not None else None
            changes.append(f"added size, colour and engraving options to {product.name}")
        if apply_own_photos(product):
            changes.append(f"added the store's own photos to {product.name}")
        elif not product.images:
            product.images.append(ProductImage(url=U(row[10][0]), alt=product.name, position=0, credit="Unsplash"))
            changes.append(f"added a photo to {product.name}")
    # Watches someone added themselves stay, in the first watch collection
    first = cats[slugify(CATEGORIES[0][0])]
    for p in Product.query.all():
        if p.category.slug not in {slugify(c[0]) for c in CATEGORIES}:
            p.category = first
            changes.append(f"moved {p.name} to {first.name}")
    db.session.flush()
    for cat in Category.query.all():
        if cat.slug not in {slugify(c[0]) for c in CATEGORIES} and not cat.products:
            db.session.delete(cat)
            changes.append(f"removed the empty {cat.name} collection")
    db.session.commit()
    return changes


def seed_settings():
    for k, v in DEFAULT_SETTINGS.items():
        if db.session.get(StoreSetting, k) is None:
            db.session.add(StoreSetting(key=k, value=v))


def seed(force=False, demo_accounts=False):
    """Seed the catalog into an empty database. Returns False if data already existed.

    No accounts are created: people register themselves. `demo_accounts=True` adds sample people and orders (tests).
    """
    # Seed whenever the catalog is empty (even if someone already registered an account)
    if Category.query.first() is not None and not force:
        return False
    rng = random.Random(7)
    now = utcnow()
    seed_settings()

    cats = []
    for i, (name, icon, desc) in enumerate(CATEGORIES):
        c = Category(name=name, slug=slugify(name), icon=icon, description=desc, position=i)
        db.session.add(c)
        cats.append(c)

    products = [_make_product(i, row, cats[row[2]], now, rng) for i, row in enumerate(PRODUCTS)]
    db.session.add_all(products)
    db.session.flush()

    db.session.add_all([
        DiscountCode(code="WELCOME10", description="10% off your first order", kind="percent", value=10),
        DiscountCode(code="STYLE500", description="₱500 off orders over ₱5,000", kind="fixed", value=50000,
                     min_subtotal_minor=500000),
        DiscountCode(code="SEASON15", description="Season sale — 15% off, limited uses", kind="percent", value=15,
                     max_uses=100, used_count=37, ends_at=now + timedelta(days=21)),
        DiscountCode(code="SUMMER25", description="Expired summer promo", kind="percent", value=25,
                     ends_at=now - timedelta(days=40), is_active=True),
    ])
    if demo_accounts:
        db.session.flush()
        seed_demo_accounts(products, rng, now)
    db.session.commit()
    return True


def seed_demo_accounts(products, rng, now):
    """OPTIONAL sample people + purchases. Used by the automated tests only; the real store starts with none."""
    def user(email, name, role, pw):
        existing = User.query.filter_by(email=email).first()
        if existing:
            return existing
        u = User(email=email, full_name=name, role=role, created_at=now - timedelta(days=rng.randint(20, 120)))
        u.set_password(pw)
        db.session.add(u)
        return u

    admin = user("admin@velora.example", "Alex Reyes", "admin", "Admin123!")
    # Two people. Each has a buyer profile and a linked seller profile (use "Switch profile" to change).
    people = []
    for email, name in (("buyer1@velora.example", "Maya Santos"), ("buyer2@velora.example", "Jonah Cruz")):
        buyer = user(email, name, "customer", "Buyer123!")
        buyer.balance_minor = STARTING_CREDIT_MINOR  # PHP 500,000 each
        user(email + SELLER_SUFFIX, name, "seller", secrets.token_urlsafe(24))
        people.append(buyer)
    db.session.flush()

    for buyer, street, phone in zip(people, ("56 Kalayaan Ave", "14 Katipunan Ave"), ("+63 917 555 0142", "+63 918 555 0187")):
        db.session.add(Address(user_id=buyer.id, label="Home", full_name=buyer.full_name, phone=phone,
                               line1=street, line2="Unit 5B", city="Quezon City",
                               region="Metro Manila", postal_code="1101", is_default=True))
        db.session.add(Address(user_id=buyer.id, label="Office", full_name=buyer.full_name, phone=phone,
                               line1="32nd St corner 5th Ave", line2="BGC Corporate Center, 12F", city="Taguig",
                               region="Metro Manila", postal_code="1634"))
    customer = people[0]

    # Orders across all statuses over the last ~30 days, so dashboards show real records
    plan = ([OrderStatus.DELIVERED] * 14 + [OrderStatus.SHIPPED] * 3 + [OrderStatus.PROCESSING] * 3 +
            [OrderStatus.CONFIRMED] * 3 + [OrderStatus.PENDING] * 2 + [OrderStatus.CANCELLED] * 2)
    buyers = people
    seq = 0
    for status in plan:
        buyer = buyers[seq % len(buyers)]
        seq += 1
        created = now - timedelta(days=rng.randint(0 if status in (OrderStatus.PENDING, OrderStatus.CONFIRMED) else 3, 29),
                                  hours=rng.randint(0, 23))
        picks = rng.sample([p for p in products if p.stock > 0], rng.randint(1, 3))
        addr = buyer.addresses[0] if buyer.addresses else None
        o = Order(number=f"VM-{created:%y%m}-{0xA00 + seq:04X}", user_id=buyer.id, status=status,
                  checkout_token=f"seed-{seq}", created_at=created, updated_at=created,
                  ship_name=buyer.full_name, ship_phone=addr.phone,
                  ship_address=addr.one_line(), subtotal_minor=0, total_minor=0)
        sub = 0
        for p in picks:
            q = rng.randint(1, 2)
            o.items.append(OrderItem(product_id=p.id, product_name=p.name, product_sku=p.sku, product_brand=p.brand,
                                     image_url=p.images[0].url if p.images else None, unit_price_minor=p.price_minor, quantity=q,
                                     size=" · ".join(x for x in (rng.choice(p.size_list) if p.size_list else "", rng.choice(p.color_list) if p.color_list else "") if x) or None,
                                     line_total_minor=p.price_minor * q))
            sub += p.price_minor * q
        o.subtotal_minor = sub
        o.shipping_minor = 0 if sub >= 250000 else 15000
        o.total_minor = sub + o.shipping_minor
        if status != OrderStatus.PENDING:
            o.confirmed_at = created + timedelta(minutes=5)
        if status in (OrderStatus.SHIPPED, OrderStatus.DELIVERED):
            o.shipped_at = created + timedelta(days=1)
        if status == OrderStatus.DELIVERED:
            o.delivered_at = created + timedelta(days=3)
        if status == OrderStatus.CANCELLED:
            o.cancelled_at, o.cancel_reason = created + timedelta(hours=2), "Changed my mind"
        method = "demo_credit"
        pay_status = "refunded" if status == OrderStatus.CANCELLED else "succeeded"
        o.payments.append(PaymentRecord(provider="demo", method=method, status=pay_status, amount_minor=o.total_minor,
                                        currency="PHP", reference=f"DEMO-SEED{seq:04d}", created_at=created,
                                        message="Seeded demo payment — no real money involved."))
        db.session.add(o)
    db.session.flush()

    # Reviews only from customers who received the product
    seen = set()
    for o in Order.query.filter_by(status=OrderStatus.DELIVERED).all():
        for it in o.items:
            key = (o.user_id, it.product_id)
            if key in seen or (o.user_id == customer.id and len(seen) % 3 == 0):
                continue  # leave some delivered items un-reviewed so the demo customer can review them
            seen.add(key)
            rating, title, body = REVIEWS[len(seen) % len(REVIEWS)]
            db.session.add(ProductReview(product_id=it.product_id, user_id=o.user_id, rating=rating, title=title,
                                         body=body, created_at=o.delivered_at + timedelta(days=1)))

    for n, buyer in enumerate(people):
        for p in products[n * 3:n * 3 + 3]:
            db.session.add(WishlistItem(user_id=buyer.id, product_id=p.id))
        if not Cart.query.filter_by(user_id=buyer.id).first():
            db.session.add(Cart(user_id=buyer.id))
        db.session.add_all([
            Notification(user_id=buyer.id, title="Welcome to Aurelune", body="Use WELCOME10 for 10% off.",
                         link="/shop/", icon="sparkles", is_read=True, created_at=now - timedelta(days=30)),
            Notification(user_id=buyer.id, title="The Moonphase Automatic is back", body="Restocked in 39 mm and 42 mm.",
                         link="/shop/p/moonphase-automatic-dress-watch", icon="watch", created_at=now - timedelta(days=1)),
        ])
    db.session.commit()
