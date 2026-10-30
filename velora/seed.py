"""Repeatable demo data (fashion, watches, jewelry, cars and gifts). Safe to run more than once: it only seeds an empty database.

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
    ("Women", "shirt", "Dresses, denim, outerwear and bags — modelled by our own team."),
    ("Men", "shirt", "Tailoring, tees, jackets, sneakers and eyewear."),
    ("Watches", "watch", "Everyday automatics, chronographs and smart watches."),
    ("Jewelry", "gem", "Gold, silver, pearls and diamonds for every day and big days."),
    ("Cars", "car", "Hand-picked pre-owned and new cars from the Velora Motors showroom."),
    ("Gifts & Gourmet", "gift", "Gift boxes, fine chocolate and coffee — including products imported from Open Food Facts."),
]

# (name, brand, category idx, price ₱, compare_at, stock, size/variant, origin, featured, sold, photo ids,
#  short description, description, materials/specs/ingredients)
PRODUCTS = [
    # Women
    ("Linen Wrap Midi Dress", "Velora Studio", 0, 2490, 2990, 18, "XS–XL", "Made in Manila, PH", True, 210,
     ["1515372039744-b8f02a3ae446"], "Breathable linen · adjustable wrap tie",
     "A wrap midi in washed linen that moves with you from brunch to evening. Adjustable tie waist, flutter sleeves and a hem that sits just below the knee.",
     "100% linen. Machine wash cold, line dry, warm iron."),
    ("Red Silk Slip Dress", "Velora Studio", 0, 3890, None, 6, "XS–L", "Made in Manila, PH", True, 140,
     ["1496747611176-843222e1e57c"], "Bias-cut mulberry silk · statement red",
     "Cut on the bias so it skims rather than clings, in a saturated red mulberry silk with fine adjustable straps.",
     "100% mulberry silk (19 momme). Dry clean or gentle hand wash."),
    ("Cropped Leather Biker Jacket", "Atelier Noir", 0, 6950, None, 9, "XS–L", "Made in Marikina, PH", True, 98,
     ["1551028719-00167b16eac5"], "Soft lambskin · asymmetric zip",
     "Our best-selling jacket in buttery lambskin with a cropped cut, asymmetric zip and quilted shoulders.",
     "Lambskin leather, viscose lining. Specialist leather clean only."),
    ("Relaxed Straight Jeans", "Denim Dept.", 0, 1990, None, 30, "24–34", "Made in Laguna, PH", False, 175,
     ["1542272604-787c3835535d"], "Rigid cotton denim · high rise",
     "A relaxed, straight-leg jean in rigid denim that softens beautifully with wear.",
     "100% cotton denim, 13 oz. Wash inside out, cold."),
    ("Structured Leather Tote", "Atelier Noir", 0, 5450, None, 12, "One size · fits 14\" laptop", "Made in Marikina, PH", False, 88,
     ["1548036328-c9fa89d128fa"], "Full-grain leather · inner zip pocket",
     "A clean-lined everyday tote in full-grain leather that holds its shape, with an inner zip pocket and magnetic closure.",
     "Full-grain cowhide, cotton twill lining."),
    # Men
    ("Tailored Wool Suit", "Maison Lune", 1, 12900, 14900, 7, "36–46", "Tailored in Manila, PH", True, 54,
     ["1507679799987-c73779587ccf"], "Two-piece · half-canvas construction",
     "A modern two-piece in fine Italian wool with a half-canvas jacket, slim lapels and flat-front trousers. Free hemming.",
     "Jacket & trousers: 100% wool. Lining: cupro. Dry clean only."),
    ("Heavyweight White Tee", "Velora Studio", 1, 790, None, 60, "S–XXL", "Made in Manila, PH", False, 320,
     ["1521572163474-6864f9cf17ab"], "240 gsm cotton · boxy fit",
     "The tee we wear under everything: dense, smooth 240 gsm cotton that keeps its shape wash after wash.",
     "100% combed cotton. Machine wash cold."),
    ("Utility Field Jacket", "Denim Dept.", 1, 4290, None, 15, "S–XL", "Made in Laguna, PH", False, 76,
     ["1591047139829-d91aecb6caea"], "Four pockets · water-resistant cotton",
     "A four-pocket field jacket in water-resistant cotton canvas with a corduroy collar.",
     "Cotton canvas with water-repellent finish. Cold wash."),
    ("Red Runner Sneakers", "Stride Lab", 1, 4590, None, 3, "EU 39–46", "Imported", True, 230,
     ["1542291026-7eec264c27ff", "1549298916-b41d501d3772"], "Cushioned runner · breathable mesh",
     "A lightweight everyday runner with a breathable mesh upper and responsive foam midsole.",
     "Mesh and synthetic upper, rubber outsole."),
    ("Tortoiseshell Sunglasses", "Optica", 1, 2890, None, 0, "One size", "Imported", False, 66,
     ["1572635196237-14b3f281503f"], "Acetate frames · UV400 lenses",
     "Classic acetate frames in warm tortoiseshell with polarised UV400 lenses and a protective case.",
     "Cellulose acetate frame, polarised lenses."),
    # Watches
    ("Minimalist Leather Strap Watch", "Horloge & Co", 2, 8900, None, 20, "38 mm", "Swiss movement", True, 150,
     ["1523275335684-37898b6baf30"], "Sapphire glass · Italian leather strap",
     "A clean, minimal dial with sapphire crystal and a quick-release Italian leather strap. Water resistant to 50 m.",
     "Case: 316L stainless steel. Movement: Swiss quartz. Water resistance: 5 ATM. 2-year warranty."),
    ("Chronograph Steel Watch", "Horloge & Co", 2, 24500, 27900, 5, "42 mm", "Swiss movement", True, 61,
     ["1522312346375-d1a52e2b99b3"], "Three-register chronograph · steel bracelet",
     "A sporty three-register chronograph on a brushed steel bracelet with tachymeter bezel.",
     "Case & bracelet: 316L steel. Movement: chronograph. Water resistance: 10 ATM. 2-year warranty."),
    ("Classic Gold-Tone Dress Watch", "Horloge & Co", 2, 15800, None, 8, "36 mm", "Swiss movement", False, 44,
     ["1524592094714-0f0654e20314"], "Slim case · dress strap",
     "A slim gold-tone dress watch that slides under a shirt cuff — made for weddings and big nights.",
     "Gold-tone PVD steel case. Movement: Swiss quartz. Water resistance: 3 ATM."),
    ("Diver Automatic 200m", "Tidewater", 2, 38900, None, 4, "41 mm", "Japanese automatic", False, 22,
     ["1547996160-81dfa63595aa"], "Automatic · 200 m water resistant",
     "A rugged automatic diver with a unidirectional ceramic bezel and luminous hands.",
     "Movement: automatic, 41 h reserve. Water resistance: 20 ATM. Sapphire crystal."),
    ("Smart Fitness Watch", "Pulse", 2, 11900, None, 25, "44 mm", "Imported", False, 130,
     ["1434056886845-dac89ffe9b56"], "Heart rate · GPS · 7-day battery",
     "Track workouts, sleep and heart rate, get notifications and pay with your wrist. Pairs with iOS and Android.",
     "Aluminium case, silicone band. GPS, heart-rate sensor. 7-day battery."),
    # Jewelry
    ("18k Gold Stacking Rings (Set of 3)", "Lumière", 3, 6800, None, 14, "Sizes 5–9", "Handmade in Meycauayan, PH", True, 120,
     ["1605100804763-247f67b3557e"], "Solid 18k gold · stack or wear alone",
     "Three fine bands — plain, twisted and beaded — in solid 18k gold, handmade by jewelers in Meycauayan.",
     "Solid 18k yellow gold. Comes in a gift box with a care cloth."),
    ("Freshwater Pearl Drop Earrings", "Lumière", 3, 3450, None, 22, "Pair", "Handmade in Meycauayan, PH", False, 95,
     ["1535632066927-ab7c9ab60908"], "Baroque pearls · gold vermeil hooks",
     "Lustrous baroque freshwater pearls on gold-vermeil hooks — each pair slightly different.",
     "Freshwater pearls, 18k gold vermeil on sterling silver."),
    ("Diamond Solitaire Pendant", "Lumière", 3, 28500, None, 3, "0.25 ct · 45 cm chain", "Certified stone", True, 31,
     ["1599643478518-a784e5dc4c8f"], "Certified 0.25 ct diamond · white gold",
     "A brilliant-cut 0.25 ct diamond in a four-claw white-gold setting on a fine adjustable chain.",
     "14k white gold. Diamond: 0.25 ct, G colour, VS2 clarity, with certificate."),
    ("Sterling Silver Chain Bracelet", "Lumière", 3, 2450, None, 40, "17 cm + 2 cm extender", "Handmade in Meycauayan, PH", False, 80,
     ["1611591437281-460bfbe1220a"], "925 silver · lobster clasp",
     "A chunky curb-chain bracelet in polished 925 sterling silver.",
     "925 sterling silver, rhodium plated to resist tarnish."),
    ("Signature Jewelry Gift Set", "Lumière", 3, 9800, 11500, 10, "Ring + earrings + necklace", "Handmade in Meycauayan, PH", False, 47,
     ["1515562141207-7a88fb7ce338"], "Three-piece set · gift boxed",
     "Our most-gifted set: a delicate ring, studs and a fine necklace, presented in a keepsake box.",
     "18k gold vermeil on sterling silver, cubic zirconia."),
    # Cars
    ("Classic Red Sports Coupe (Pre-owned)", "Velora Motors", 4, 3850000, None, 1, "2019 · 21,400 km", "Velora Motors showroom, Taguig", True, 2,
     ["1494976388531-d1058494cdd8"], "V8 · automatic · one owner",
     "A one-owner red coupe with full service history, inspected bumper to bumper by our technicians. Price includes registration transfer. (Demo listing.)",
     "Engine: 5.0 L V8. Transmission: 10-speed automatic. Mileage: 21,400 km. Colour: red. Warranty: 12 months (demo)."),
    ("Silver Luxury Sports Car (Pre-owned)", "Velora Motors", 4, 4800000, 5200000, 1, "2020 · 15,900 km", "Velora Motors showroom, Taguig", True, 1,
     ["1503376780353-7e6692767b70"], "Turbo flat-six · PDK-style dual clutch",
     "A low-mileage silver sports car with sports exhaust, heated seats and a clean history report. (Demo listing.)",
     "Engine: 3.0 L twin-turbo flat-six. Transmission: 8-speed dual clutch. Mileage: 15,900 km. Colour: silver."),
    ("Midnight Muscle Coupe (Pre-owned)", "Velora Motors", 4, 2650000, None, 1, "2018 · 34,200 km", "Velora Motors showroom, Taguig", False, 3,
     ["1552519507-da3b142c6e3d"], "V8 · manual · track pack",
     "A dark, rumbling coupe with a six-speed manual and track package. Fresh tyres and brakes. (Demo listing.)",
     "Engine: 6.2 L V8. Transmission: 6-speed manual. Mileage: 34,200 km."),
    ("Electric Crossover SUV", "Velora Motors", 4, 2190000, None, 2, "2024 · brand new", "Velora Motors showroom, Taguig", False, 4,
     ["1580273916550-e323be2ae537"], "Up to 450 km range · fast charging",
     "A brand-new all-electric family crossover with 450 km range, fast charging and a home charger included. (Demo listing.)",
     "Battery: 75 kWh. Range: up to 450 km. Charging: 10–80% in 30 min (DC). Seats: 5."),
    # Gifts & Gourmet
    ("Luxury Gift Box", "Velora Gifting", 5, 1450, None, 30, "Medium box", "Packed in Manila, PH", True, 140,
     ["1549465220-1a8b9238cd48"], "Hand-wrapped · personal note included",
     "We wrap your purchase in our signature box with tissue, ribbon and a handwritten note.",
     "Rigid recycled-board box, cotton ribbon."),
    ("72% Dark Chocolate Bar", "Cacao Collective", 5, 245, None, 80, "60 g bar", "Davao, PH", False, 300,
     ["1511381939415-e44015466834"], "Bean-to-bar · red fruit & molasses",
     "Made from fermented Davao cacao roasted and stone-ground in small batches.",
     "Cacao beans, cane sugar, cocoa butter"),
    ("Single-Origin Coffee Beans", "Velora Roastery", 5, 685, None, 40, "250 g", "Benguet, PH", False, 186,
     ["1447933601403-0c6688de566e"], "Brown sugar, orange & almond",
     "Highland Arabica from the Cordilleras, roasted weekly. The perfect add-on gift.",
     "100% Arabica coffee beans"),
    ("Scented Soy Candle", "Velora Home", 5, 890, None, 28, "220 g · 45 hr burn", "Manila, PH", False, 65,
     ["1603006905003-be475563bc59"], "Hinoki & fig · reusable vessel",
     "Clean-burning soy wax scented with Japanese cypress and green fig.",
     "Soy wax, cotton wick, fragrance oils"),
]

REVIEWS = [
    (5, "My new favourite piece", "The quality is even better in person. I've worn it three times this week."),
    (4, "Lovely, runs slightly small", "Beautiful finish and packaging. I'd size up if you're between sizes."),
    (5, "Worth every peso", "Exactly as described and delivery was quick. Looks like the photos."),
    (5, "Gift-worthy", "Bought one for myself and one as a gift. Everyone asked where it was from."),
    (3, "Good, not perfect", "Well made, but the colour is a little different from my screen. Service was great."),
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
        DiscountCode(code="STYLE500", description="₱500 off orders over ₱5,000", kind="fixed", value=50000,
                     min_subtotal_minor=500000),
        DiscountCode(code="SEASON15", description="Season sale — 15% off, limited uses", kind="percent", value=15,
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
        picks = rng.sample([p for p in products if p.stock > 0 and p.category is not cats[4]], rng.randint(1, 3))
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
        Notification(user_id=customer.id, title="The Red Silk Slip Dress is back", body="Restocked in sizes XS–L.",
                     link="/shop/p/red-silk-slip-dress", icon="shirt", created_at=now - timedelta(days=1)),
    ])
    db.session.commit()
    return True
