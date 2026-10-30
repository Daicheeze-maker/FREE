"""Repeatable demo data. Safe to run more than once: it only seeds an empty database.

Photos are hot-linked from Unsplash (free to use under the Unsplash License). If any URL
fails to load, the storefront swaps in a local placeholder automatically.
"""
import random
from datetime import timedelta

from .extensions import db
from .models import (DEFAULT_SETTINGS, Address, Cart, Category, DiscountCode, Notification, Order, OrderItem,
                     OrderStatus, PaymentRecord, Product, ProductImage, ProductReview, StoreSetting, User,
                     WishlistItem, utcnow)
from .services.catalog import slugify


def U(photo_id, w=900):
    return f"https://images.unsplash.com/photo-{photo_id}?w={w}&q=80&auto=format&fit=crop"


CATEGORIES = [
    ("Coffee & Tea", "coffee", "Single-origin beans, whole-leaf teas and slow-morning rituals."),
    ("Pantry", "wheat", "Oils, grains, honey and the staples that make weeknights better."),
    ("Snacks & Sweets", "cookie", "Bean-to-bar chocolate, roasted nuts and small-batch bakes."),
    ("Wellness", "leaf", "Ceremonial matcha, botanicals and gentle self-care."),
    ("Fresh & Bakery", "croissant", "Naturally leavened breads and the week's best produce."),
    ("Home & Kitchen", "cooking-pot", "Hand-thrown ceramics and objects for a considered table."),
]

# (name, brand, category idx, price ₱, compare_at, stock, size, origin, featured, sold, photo ids, short, desc, ingredients)
PRODUCTS = [
    ("Sidama Natural Coffee Beans", "Velora Roastery", 0, 685, None, 42, "250 g", "Sidama, Ethiopia", True, 186,
     ["1447933601403-0c6688de566e", "1495474472287-4d71bcdd2085"], "Blueberry, jasmine & cacao nib · light roast",
     "A naturally processed lot from smallholders in Sidama, roasted lightly in our studio every Tuesday so it arrives within days of roasting. Expect a syrupy body with ripe blueberry, jasmine and a cacao-nib finish. Brilliant as pour-over or a bright espresso.",
     "100% Arabica coffee beans"),
    ("Benguet Highland Medium Roast", "Velora Roastery", 0, 520, None, 60, "250 g", "Atok, Benguet, PH", True, 241,
     ["1559056199-641a0ac8b55e"], "Brown sugar, orange & toasted almond",
     "Grown at 1,600 m in the Cordilleras and washed at the farm, this medium roast is our everyday cup — sweet, balanced and forgiving in any brewer.",
     "100% Arabica coffee beans"),
    ("Cold Brew Concentrate", "Velora Roastery", 0, 340, 395, 4, "500 ml", "Manila, PH", False, 133,
     ["1461023058943-07fcbe16d735"], "Steeped 18 hours · dilute 1:1",
     "Coarse-ground Benguet beans steeped cold for 18 hours, then double-filtered. Smooth and chocolatey with low acidity. Keep refrigerated; best within 10 days of opening.",
     "Filtered water, Arabica coffee"),
    ("First Flush Darjeeling", "Leaf & Ledger", 0, 760, None, 25, "100 g loose leaf", "Darjeeling, India", False, 58,
     ["1576092768241-dec231879fc3"], "Muscatel, apricot & spring flowers",
     "Picked in the first spring flush, this whole-leaf Darjeeling is delicate and floral with the signature muscatel note. Steep 3 minutes at 90°C.",
     "Black tea (Camellia sinensis)"),
    ("Chamomile & Lemon Verbena", "Leaf & Ledger", 3, 420, None, 38, "20 pyramid sachets", "Egypt & Spain", False, 92,
     ["1556679343-c7306c1976bc"], "Caffeine-free evening blend",
     "Whole Egyptian chamomile flowers with lemon verbena and a whisper of lavender — our most-gifted wind-down tea.",
     "Chamomile flowers, lemon verbena, lavender"),
    ("Ceremonial Grade Matcha", "Kumo Tea House", 3, 1450, 1650, 18, "30 g tin", "Uji, Japan", True, 164,
     ["1515823064-d6e0c04616a7"], "Shade-grown · stone-ground",
     "Shade-grown tencha from Uji, stone-ground into a vivid green powder. Umami-rich with a sweet, grassy finish and none of the bitterness of culinary grades.",
     "100% stone-ground green tea leaves"),
    ("Cold-Pressed Extra Virgin Olive Oil", "Casa Oliva", 1, 980, None, 30, "500 ml", "Jaén, Spain", True, 149,
     ["1474979266404-7eaacbcd87c5"], "Picual · harvested early for peppery finish",
     "Early-harvest Picual olives, cold-pressed within hours of picking. Grassy, green tomato and a peppery finish — for finishing, dipping and dressing.",
     "100% extra virgin olive oil"),
    ("Raw Wildflower Honey", "Bukid Apiary", 1, 450, None, 3, "350 g jar", "Bukidnon, PH", True, 212,
     ["1587049352846-4a222e784d38"], "Unfiltered · single-apiary",
     "Unheated and lightly strained honey from hives beside wild coffee and calamansi blossoms in Bukidnon. Naturally crystallises — a sign it's truly raw.",
     "Raw honey"),
    ("Bronze-Cut Rigatoni", "Pastificio Verde", 1, 295, None, 54, "500 g", "Gragnano, Italy", False, 120,
     ["1551462147-ff29053bfc14"], "Slow-dried 48 hours",
     "Durum wheat semolina extruded through bronze dies for a rough surface that holds sauce, then slow-dried for two days.",
     "Durum wheat semolina, water"),
    ("Toasted Coconut Granola", "Morning Field", 1, 365, None, 47, "400 g", "Laguna, PH", False, 176,
     ["1490474418585-ba9bad8fd0ea"], "Oats, cashew & muscovado",
     "Rolled oats baked slow with cashews, coconut chips and Antique muscovado sugar. Clustery, not too sweet.",
     "Rolled oats, cashews, coconut, muscovado sugar, coconut oil, sea salt"),
    ("Smoked Paprika & Spice Trio", "Spice Atlas", 1, 540, None, 22, "3 × 40 g", "Various", False, 44,
     ["1596040033229-a9821ebd058d"], "Pimentón, sumac & za'atar",
     "Three workhorse spices in reusable tins: La Vera smoked pimentón, bright Turkish sumac and a thyme-forward za'atar.",
     "Smoked paprika; sumac, salt; thyme, sesame, sumac, salt"),
    ("72% Davao Dark Chocolate", "Cacao Collective", 2, 245, None, 80, "60 g bar", "Davao, PH", True, 301,
     ["1511381939415-e44015466834"], "Bean-to-bar · red fruit & molasses",
     "Made from fermented Davao cacao roasted and stone-ground in small batches. Notes of red fruit, molasses and a long cocoa finish.",
     "Cacao beans, cane sugar, cocoa butter"),
    ("Sea Salt Rosemary Almonds", "Velora Pantry", 2, 310, None, 0, "180 g", "California, USA", False, 97,
     ["1508061253366-f7da158b6d46"], "Dry-roasted, no seed oils",
     "Whole almonds dry-roasted and tossed with Pangasinan sea salt and fresh rosemary.",
     "Almonds, rosemary, sea salt"),
    ("Brown Butter Chocolate Chip Cookies", "Velora Bakehouse", 2, 380, None, 16, "Box of 6", "Manila, PH", False, 158,
     ["1558961363-fa8fdf82db35"], "Baked daily · 72% chocolate",
     "Brown butter dough rested 48 hours, studded with chopped Davao chocolate and finished with flaky salt.",
     "Wheat flour, butter, brown sugar, dark chocolate, eggs, sea salt, vanilla"),
    ("Trail Mix No. 3", "Velora Pantry", 2, 275, None, 35, "250 g", "Manila, PH", False, 64,
     ["1599599810769-bcde5a160d32"], "Cashew, pili, cranberry & cacao nib",
     "Our hiking mix with Bicol pili nuts, roasted cashews, tart cranberries and cacao nibs.",
     "Cashews, pili nuts, dried cranberries, cacao nibs, pumpkin seeds"),
    ("Country Sourdough Loaf", "Velora Bakehouse", 4, 320, None, 12, "900 g", "Manila, PH", True, 190,
     ["1509440159596-0249088772ff"], "36-hour ferment · baked mornings",
     "Naturally leavened with our 6-year-old starter, long-fermented for flavour and a blistered, crackling crust.",
     "Wheat flour, whole wheat flour, water, salt, natural leaven"),
    ("Butter Croissants", "Velora Bakehouse", 4, 360, None, 9, "Pack of 4", "Manila, PH", False, 140,
     ["1555507036-ab1f4038808a"], "Laminated with cultured butter",
     "Three-day laminated croissants with cultured butter — bake from frozen in 18 minutes for a just-baked morning.",
     "Wheat flour, cultured butter, milk, sugar, yeast, salt"),
    ("Hass Avocado Box", "Highland Growers", 4, 420, None, 20, "4 pieces", "Bukidnon, PH", False, 71,
     ["1523049673857-eb18f1d7b578"], "Ripens in 2–3 days",
     "Creamy Hass avocados from a family farm in Bukidnon, picked mature and delivered just shy of ripe.",
     None),
    ("Seasonal Fruit Crate", "Highland Growers", 4, 890, 990, 14, "Approx. 3 kg", "Mindanao, PH", True, 88,
     ["1610832958506-aa56368176cf"], "Whatever is best this week",
     "A rotating crate of the week's best fruit from partner farms — mangoes, lakatan, pomelo or dalandan depending on harvest.",
     None),
    ("Green Recovery Smoothie Pack", "Morning Field", 3, 480, None, 26, "5 frozen packs", "Laguna, PH", False, 49,
     ["1505252585461-04db1eb84625"], "Spinach, mango, chia & moringa",
     "Pre-portioned frozen smoothie packs — just add milk or water and blend.",
     "Mango, banana, spinach, moringa, chia seeds"),
    ("Brightening Vitamin C Serum", "Botanica Lab", 3, 1180, None, 21, "30 ml", "Seoul, KR", False, 77,
     ["1620916566398-39f1143ab7be"], "10% ascorbyl glucoside · fragrance-free",
     "A lightweight, fragrance-free serum with stable vitamin C and niacinamide for a brighter, even tone.",
     "Water, ascorbyl glucoside, niacinamide, glycerin, panthenol"),
    ("Cork Yoga Mat", "Grounded", 3, 2650, 2990, 7, "183 × 61 cm", "Portugal", False, 34,
     ["1544367567-0f2fcb009e0b"], "Natural cork over rubber · grippy when wet",
     "Natural cork top over plant-based rubber — naturally antimicrobial and grippier as you sweat.",
     None),
    ("Stoneware Mug Set", "Tahanan Ceramics", 5, 1350, None, 15, "Set of 2 · 300 ml", "Laguna, PH", True, 82,
     ["1514228742587-6b1558fcca3d"], "Hand-thrown · speckled glaze",
     "Hand-thrown by a two-person studio in Laguna, each mug is slightly different with a speckled oat glaze. Dishwasher safe.",
     None),
    ("Hinoki & Fig Soy Candle", "Tahanan Ceramics", 5, 890, None, 28, "220 g · 45 hr burn", "Manila, PH", False, 65,
     ["1603006905003-be475563bc59"], "Cotton wick · reusable vessel",
     "Clean-burning soy wax scented with Japanese cypress and green fig, poured into a reusable stoneware cup.",
     "Soy wax, cotton wick, fragrance oils"),
]

REVIEWS = [
    (5, "My new everyday beans", "Bright, sweet and arrives so fresh. I've switched my whole office over."),
    (4, "Lovely, slightly pricey", "Beautiful quality and packaging. Would love a bigger size option."),
    (5, "Worth every peso", "Exactly as described and delivery was quick. The tasting notes are spot on."),
    (5, "Gift-worthy", "Bought one for myself and two as gifts. Everyone asked where it was from."),
    (3, "Good but not for me", "Well made, just a little too intense for my taste. Service was great."),
    (4, "Solid repeat purchase", "Third order now. Consistent and well packed every time."),
]


def seed_settings():
    for k, v in DEFAULT_SETTINGS.items():
        if db.session.get(StoreSetting, k) is None:
            db.session.add(StoreSetting(key=k, value=v))


def seed(force=False):
    """Seed demo data into an empty database. Returns False if data already existed."""
    if User.query.first() is not None and not force:
        return False
    rng = random.Random(7)
    now = utcnow()
    seed_settings()

    cats = []
    for i, (name, icon, desc) in enumerate(CATEGORIES):
        c = Category(name=name, slug=slugify(name), icon=icon, description=desc, position=i)
        db.session.add(c)
        cats.append(c)

    products = []
    for i, (name, brand, ci, price, compare, stock, size, origin, featured, sold, photos, short, desc, ingr) in enumerate(PRODUCTS):
        p = Product(name=name, slug=slugify(name), sku=f"VM-{1000 + i}", brand=brand, category=cats[ci],
                    short_description=short, description=desc, price_minor=price * 100,
                    compare_at_minor=compare * 100 if compare else None, stock=stock, size_label=size,
                    origin=origin, is_featured=featured, sold_count=sold, ingredients=ingr,
                    created_at=now - timedelta(days=60 - i * 2 if i < 18 else rng.randint(1, 12)))
        for pos, pid in enumerate(photos):
            p.images.append(ProductImage(url=U(pid), alt=f"{name} — {short}", position=pos, credit="Unsplash"))
        db.session.add(p)
        products.append(p)
    db.session.flush()

    def user(email, name, role, pw):
        u = User(email=email, full_name=name, role=role, created_at=now - timedelta(days=rng.randint(20, 120)))
        u.set_password(pw)
        db.session.add(u)
        return u

    admin = user("admin@velora.example", "Alex Reyes", "admin", "Admin123!")
    seller = user("seller@velora.example", "Sam Villanueva", "seller", "Seller123!")
    customer = user("customer@velora.example", "Maya Santos", "customer", "Customer123!")
    extra = [user(f"{n.split()[0].lower()}@example.com", n, "customer", "Customer123!")
             for n in ("Jonah Cruz", "Bea Lim", "Paolo Garcia", "Ines Tan", "Rafa Dizon")]
    test_acct = user("test.account@example.com", "QA Test Account", "customer", "Customer123!")
    db.session.flush()

    for u in [customer] + extra:
        db.session.add(Address(user_id=u.id, label="Home", full_name=u.full_name, phone="+63 917 555 0142",
                               line1=f"{rng.randint(10, 400)} Kalayaan Ave", line2="Unit 5B", city="Quezon City",
                               region="Metro Manila", postal_code="1101", is_default=True))
    db.session.add(Address(user_id=customer.id, label="Office", full_name=customer.full_name, phone="+63 917 555 0142",
                           line1="32nd St corner 5th Ave", line2="BGC Corporate Center, 12F", city="Taguig",
                           region="Metro Manila", postal_code="1634"))

    db.session.add_all([
        DiscountCode(code="WELCOME10", description="10% off your first order", kind="percent", value=10),
        DiscountCode(code="PANTRY200", description="₱200 off orders over ₱1,500", kind="fixed", value=20000,
                     min_subtotal_minor=150000),
        DiscountCode(code="HARVEST15", description="Harvest sale — 15% off, limited uses", kind="percent", value=15,
                     max_uses=100, used_count=37, ends_at=now + timedelta(days=21)),
        DiscountCode(code="SUMMER25", description="Expired summer promo", kind="percent", value=25,
                     ends_at=now - timedelta(days=40), is_active=True),
    ])

    # Orders across all statuses over the last ~30 days, so dashboards show real records
    plan = ([OrderStatus.DELIVERED] * 14 + [OrderStatus.SHIPPED] * 3 + [OrderStatus.PROCESSING] * 3 +
            [OrderStatus.CONFIRMED] * 3 + [OrderStatus.PENDING] * 2 + [OrderStatus.CANCELLED] * 2)
    buyers = [customer] * 6 + extra
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
                  ship_name=buyer.full_name, ship_phone="+63 917 555 0142",
                  ship_address="Kalayaan Ave, Quezon City, Metro Manila, 1101, Philippines", subtotal_minor=0, total_minor=0)
        sub = 0
        for p in picks:
            q = rng.randint(1, 2)
            o.items.append(OrderItem(product_id=p.id, product_name=p.name, product_sku=p.sku, product_brand=p.brand,
                                     image_url=p.images[0].url, unit_price_minor=p.price_minor, quantity=q,
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
        method = "cod" if seq % 4 == 0 else "demo_approve"
        pay_status = ("refunded" if status == OrderStatus.CANCELLED and method != "cod" else
                      "pending" if method == "cod" and status != OrderStatus.DELIVERED else "succeeded")
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

    for p in products[:3]:
        db.session.add(WishlistItem(user_id=customer.id, product_id=p.id))
    db.session.add(Cart(user_id=customer.id))
    db.session.add_all([
        Notification(user_id=customer.id, title="Welcome to Velora Market", body="Use WELCOME10 for 10% off.",
                     link="/shop/", icon="sparkles", is_read=True, created_at=now - timedelta(days=30)),
        Notification(user_id=customer.id, title="Your Sidama beans are back", body="Roasted this Tuesday.",
                     link="/shop/p/sidama-natural-coffee-beans", icon="coffee", created_at=now - timedelta(days=1)),
    ])
    db.session.commit()
    return True
