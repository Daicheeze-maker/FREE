# Aurelune

A full-stack demo e-commerce store that sells **only watches**, and lets the buyer choose the **case size, colour and an optional engraving** on every one. It's built with **Python 3.11+ / Flask / SQLAlchemy / SQLite** and has four role-based experiences: guest, customer, seller and administrator. It integrates two real external APIs, **Open Food Facts** and **Frankfurter**, and adds smooth GSAP animation.

It runs directly on Windows 10/11 or Ubuntu, on bare metal or inside a virtual machine. Docker is not needed.

> **Demo store.** Payments are *simulated*. No card numbers, CVVs or bank details are ever requested, and no money moves.

---

## 1. Quick start

### Ubuntu / Linux (also macOS)

```bash
sudo apt update && sudo apt install -y python3 python3-venv python3-pip   # Ubuntu 22.04+/24.04
cd velora-market            # the project folder
bash start.sh               # first run sets everything up; then opens http://127.0.0.1:5000
```

### Windows 10/11 — the easy way

1. Install Python 3.11+ from python.org and tick **“Add python.exe to PATH”** (one time only).
2. **Double-click `start.bat`** in the project folder. That's it.
   - The first time it sets everything up (1–2 minutes, needs internet), then starts the store and **opens your browser**.
   - Every time after that it starts in a few seconds.
   - Press **Ctrl+C** in its window to stop the store.

In **VS Code** you can also press **F5** (Run → *Run Aurelune*) or use **Terminal → Run Build Task** (Ctrl+Shift+B), which runs `start.bat`.

Prefer typing commands? In a terminal inside the project folder: `.\start.bat` (PowerShell) or `start.bat` (Command Prompt). The older `scripts\setup.bat` and `scripts\run.bat` still work too.

### Manual setup (any OS)

```bash
python -m venv .venv
# Linux/macOS: source .venv/bin/activate     Windows: .venv\Scripts\activate
python -m pip install -r requirements.txt
cp .env.example .env          # then put a random value in SECRET_KEY
python -m flask --app wsgi init-db      # create/upgrade the schema via migrations (non-destructive)
python -m flask --app wsgi seed         # demo data; does nothing if the DB already has users
python serve.py
```

**Windows says `flask.exe` / `pip.exe` "was blocked by your organization's Device Guard policy"?** Some school and work PCs block programs inside `.venv\Scripts`. All the scripts here call everything through Python (`python -m flask …`, `python -m pip …`), which isn't blocked. Use the same form for any command in this README, e.g. `python -m flask --app wsgi reset-demo --yes-delete-everything`.

### Store name

The store is called **Aurelune**. To use another name, put `STORE_NAME=Your Name` in `.env` (logo, page titles, emails and welcome messages follow it).

### Accounts (you create them)

The store starts with **no accounts and no demo logins**. Click **Create account** (top right) and register. Your account is saved in the database (`instance/velora.db`) with a securely hashed password, and you sign in with the same email and password every time.

- Every new **buyer** starts with **₱500,000 of demo credit**, spent at checkout (an admin can reset it under *Admin → Users → (buyer) → Demo credit*).
- On **Create account** you choose **Shop** or **Sell**. *Sell* signs you in to your seller profile and opens **Seller studio**. **Admins** see every seller (and when they last signed in) under **Admin → Active sellers**.
- Every buyer also gets a **linked seller profile**: open the account menu and choose **Switch to seller profile** (and back). What a buyer purchases shows up in the *Orders* of the seller profile, which can ship it and mark it delivered. Make a second account to get a second buyer + seller.
- **An administrator** is created from the terminal (it is never self-registered):

  ```
  python -m flask --app wsgi create-admin
  ```

  On Windows just **double-click `create-admin.bat`** (it uses the project's own Python, so no "No module named flask").

  It asks for an email, a name and a password. Sign in with them at the normal sign-in page.
- Old copies of this project had sample accounts (`buyer1@velora.example`, …). `start.bat` / `start.sh` remove those automatically, together with their sample orders (an account that has a real order is kept).

Discount codes: `WELCOME10`, `STYLE500` (₱500 off ₱5,000+), `SEASON15` (limited uses), and `SUMMER25` (expired, to show validation).

### Model photos: professional photos (free) or your own

The five big site photos (homepage hero, lookbook tile, sale banner, sign-in and register pages) start as **placeholders**, and so does any product without a photo. Sign in as a seller and open **Seller studio → Model photos**:

- **Find professional model photos (free, from Pexels):**
  1. One-time: click **Set up free Pexels photos**, sign up at [pexels.com/api](https://www.pexels.com/api/) (free, one minute), copy your key and paste it into the page. (Or put `PEXELS_API_KEY=…` in `.env`.)
  2. Click **Auto-fill with model photos** to fill every empty spot in one click, or use **Find a photo** on a spot to search and pick one yourself. For a product, open it under *Products* and click **Find a model photo**. To fix many products at once, open **Products** and click **Fill missing & broken photos**: it checks every product photo, replaces missing or dead ones (products with no photo first) using a search specific to each product, such as “tortoiseshell sunglasses”, up to 30 per click.
  3. Each pick is **downloaded into your store** (`instance/uploads/`), so it never breaks, and the photographer is credited on the product page and the About page.
- **Use your own photos:** upload one per spot on the same page, or on a product's edit page (keep “Use the new photo as the cover image” ticked). For many at once, drop files into `model-photos/` (see `model-photos/README.txt`) and run `python -m flask --app wsgi load-model-photos`.

Portrait photos (taller than wide) look best. Every image is checked, resized and converted to WebP. Pexels photos are free to use under the [Pexels license](https://www.pexels.com/license/); don't use a stock model's photo to suggest that person endorses your store.

### The collections and the watches

| Collection | Examples |
|---|---|
| Dress Watches | minimalist leather strap, gold-tone dress watch, moonphase automatic, skeleton |
| Dive Watches | automatic diver 200 m, titanium diver, rubber-strap diver |
| Chronographs | steel chronograph, racing chronograph, tachymeter sport chrono, Spectrum Chronograph (10 colours, 360° view) |
| Field & Pilot | field automatic, pilot aviator, explorer on canvas |
| Smart Watches | fitness watch, hybrid watch, GPS sport watch |
| Ladies Watches | rose gold bracelet, pearl dial, petite mesh |

That is 20 watches. The **Spectrum Chronograph** comes in ten colour editions, each with its own photo, and has a **360° View**: drag the watch (or use the arrow keys) to turn it all the way around; picking a colour changes the photo and the 360° view. The photos of 10 of them, and of the homepage and sign-in spots, are the store's own (from the owner's Google Drive folder, saved in `velora/static/img/watches/`, so they load even offline); the others use stock photos. **Every watch has options** that the buyer picks on its page:

- **Case size** (for example 38 mm / 42 mm / 44 mm), **colour** (with colour swatches), and a **personal engraving** (up to 20 characters, with its own fee, on watches that offer it).
- Size and colour are required before a watch can go into the bag; the same watch in two different sizes, colours or engravings is two bag lines (stock is shared). The engraving fee is added **by the server**, never by the browser, and the chosen options are saved on the order and shown in the bag, checkout, confirmation, order history, seller order page and the orders CSV.
- Sellers set each watch's sizes, colours, engraving fee and the most characters allowed in **Seller studio → Products → (watch)**.

**Updating from an older version (fashion, shoes, bags…)?** `start.bat` / `start.sh` convert it automatically and keep your accounts, orders, settings and uploaded photos: clothing, shoes, accessories, jewelry, bags and gift products are removed (past orders keep their own copy of what was bought), the watches and their options are added, and watches you added yourself are kept. It prints what it changed, and a second start changes nothing.

---

## 2. Running in a Virtual Machine

The app needs **outbound internet only for the two optional APIs** and for product photos, which are hot-linked from Unsplash. Shopping, cart, checkout and the dashboards all work offline from the local SQLite database. When an API is unreachable, the related feature shows a clear “unavailable” state.

### Networking modes

| Goal | VM network setting | What to run |
|---|---|---|
| Use the store **inside the VM** only | **NAT** (default in VirtualBox/VMware/Hyper-V) | `scripts/run.sh` → `http://127.0.0.1:5000` in the VM's browser |
| Open the store **from the host or another device on your LAN** | **Bridged** adapter (VM gets a LAN IP) | `HOST=0.0.0.0 scripts/run.sh` |
| Open it **from the host only** | **Host-only** adapter (plus NAT for internet) | `HOST=0.0.0.0 scripts/run.sh` |
| Keep NAT but reach it from the host | NAT + **port forwarding** host 5000 → guest 5000 | `HOST=0.0.0.0 scripts/run.sh`, then `http://127.0.0.1:5000` on the host |

**Find the VM's IP address**
- Ubuntu: `ip -4 addr show` (look for `inet 192.168.x.x` on the bridged or host-only adapter)
- Windows: `ipconfig` (look for *IPv4 Address*)

Then browse to `http://<VM-IP>:5000` from the other device.

**Open the firewall port** (only when you bind to `0.0.0.0`)
- Ubuntu (ufw): `sudo ufw allow 5000/tcp` (or `8000/tcp` for Gunicorn)
- Windows (admin PowerShell):
  `New-NetFirewallRule -DisplayName "Velora 5000" -Direction Inbound -Protocol TCP -LocalPort 5000 -Action Allow -Profile Private`

**Safety defaults.** The server binds to `127.0.0.1` unless you set `HOST=0.0.0.0` (or `BIND=0.0.0.0:8000` for Gunicorn), so nothing is exposed to the network by default. Don't port-forward it to the public internet. If you serve it over HTTPS (for example behind nginx with a certificate), set `SESSION_COOKIE_SECURE=1` and `VELORA_ENV=production`.

### Production-style serving on Linux (Gunicorn)

```bash
VELORA_ENV=production bash scripts/run_gunicorn.sh                  # 127.0.0.1:8000, 3 workers
BIND=0.0.0.0:8000 WORKERS=4 bash scripts/run_gunicorn.sh             # reachable on the LAN
# equivalent raw command:
gunicorn wsgi:app --bind 127.0.0.1:8000 --workers 3 --timeout 30 --access-logfile -
```

In production mode the app refuses to start without `SECRET_KEY`. On Windows, use `python serve.py`, which runs Waitress, a production-grade WSGI server.

### Persistent storage and paths

The SQLite database and uploaded images live in `instance/` by default (`instance/velora.db`, `instance/uploads/`). Override them with `VELORA_DB_PATH` / `VELORA_UPLOAD_DIR` / `DATABASE_URL` in `.env`. For example, you can point them at a VM shared folder or a separate disk. Relative paths resolve from the project folder, not the working directory, so the scripts work from anywhere.

### Health check

`GET /healthz` returns `{"status":"ok","database":"ok"}` with HTTP 200. If the database is unreachable it returns 503.

---

## 3. The four user profiles

| Profile | How to get it | Dashboard | Can do |
|---|---|---|---|
| **Guest shopper** | Not signed in | Storefront | Browse, search, filter (aisle / maker / price / availability), sort (featured, newest, popular, price, rating), view products, reviews and nutrition, use a session bag, switch currency, register / sign in. No access to account, seller or admin pages (server-side redirects or 403). |
| **Customer** | Self-registration (**Create account**); signs in with their own password. A linked seller profile is created with it | `/account/` — stats, live tracker for the active order, recent orders, notifications, wishlist, “waiting for your review”, recently viewed | Persistent bag (merged from the guest bag at login), wishlist, addresses, discount codes, address-free demo checkout, order history and tracking, cancel while *Pending/Confirmed*, review only **delivered** purchases (one per product), notifications, profile and password change. |
| **Seller / store manager** | Assigned by an admin, or the linked seller profile every buyer gets (use *Switch to seller profile* in the account menu) | `/seller/` — revenue chart, KPIs, fulfilment queue, order pipeline, low-stock alerts with one-click restock, top sellers, latest feedback | **Model photos**, product CRUD, archive and restore, secure image uploads, categories, inventory, order processing with enforced status transitions, promotions and discount codes, review moderation and public replies, **Open Food Facts import**, CSV exports. This is a single-store catalog, not a multi-vendor marketplace. |
| **Administrator** | Seeded, or created with `python -m flask --app wsgi create-admin` | `/admin/` (blue “Admin console” theme) — store KPIs, 30-day revenue, integrations status, audit feed, accounts by role, inventory value | Everything a seller can do, plus users and roles, enable/disable accounts, clear login locks, sales and inventory reports, store settings (shipping rules, low-stock threshold, announcement), **API health with live test buttons**, and a full **audit log**. |

Roles are stored only in the database. Registration has no role field, so a submitted `role=admin` is ignored. Every protected route checks the role on the server. Admins can't demote or disable themselves, and at least one active admin always remains.

---

## 4. External API integrations

These are real HTTP integrations made with `requests` (Open Food Facts and Frankfurter run in the store; Pexels is used only by staff to pick photos). Each call is recorded on the admin **API health** page (last success, latency, error count, last error). The admin can trigger a live test there.

### Open Food Facts — `velora/services/openfoodfacts.py`
- **Search:** `GET {OFF_BASE_URL}/cgi/search.pl?search_terms=…&search_simple=1&action=process&json=1&page=&page_size=&fields=…`
- **Product by barcode:** `GET {OFF_BASE_URL}/api/v2/product/{barcode}.json?fields=…`
- Read-only and no API key. Every request sends a descriptive `User-Agent: VeloraMarket/1.0 (<VELORA_CONTACT_EMAIL>)` as OFF's usage policy asks. Searches happen only when staff explicitly ask for one, and HTTP 429 (rate limited) gets a clear message.
- **Where it's used:** Open Food Facts is a food database, so imports are an extra tool (the store itself only sells watches). *Seller studio → Import · Open Food Facts* shows real results (image if any, brand, quantity, categories, ingredients, Nutri-Score, and how complete the data is) with skeleton loading, empty and error states. **Import** re-fetches the product by barcode on the server, so data posted by the browser is never trusted. It validates and normalizes the record (trims, length limits, numeric nutrients only, https images, valid barcode and grade) and stores it locally as a draft at your price and stock. Imported products look like hand-made ones, and the product page shows ingredients, allergens, a Nutri-Score badge and a per-100 g nutrition table, with attribution. A *Refresh from Open Food Facts* button re-syncs a product. The storefront never calls OFF, so imported products keep working offline.

### Frankfurter — `velora/services/currency.py`
- `GET {FRANKFURTER_BASE_URL}/latest?base=PHP&symbols=USD,EUR,GBP,JPY,SGD,AUD` (default base URL `https://api.frankfurter.dev/v1`). No key needed. Rates are ECB reference rates, updated on working days.
- The header currency picker offers PHP, USD, EUR, GBP, JPY, SGD and AUD. Rates are cached in `exchange_rate_cache` for `FX_CACHE_HOURS` (default 6). Rates are parsed with `Decimal(str(value))`, never floats.
- **Fallbacks:** if a refresh fails, the app uses the last cached rate and labels it *cached*. With no rate at all, it shows prices in PHP with an “unavailable” note. After a failure it waits `API_RETRY_BACKOFF_MINUTES` before retrying, so an offline VM doesn't stall page loads.
- Converted prices carry a “≈” and a note saying **orders are always charged in PHP**. Orders, totals and payments are stored only in PHP minor units (centavos).

> **Note on verification:** this project was built in a sandbox with no access to either API, so the endpoints and response shapes follow the published docs and the automated tests mock them. Please run `python -m flask --app wsgi refresh-rates` and press the **API health → test** buttons once in your VM to confirm live connectivity. If a provider moves its base URL, change `OFF_BASE_URL` / `FRANKFURTER_BASE_URL` in `.env`.

---

### Mapbox — `velora/services/mapbox.py` (address suggestions)
- When someone types a street address (checkout, *My addresses*), the page asks **this server** (`GET /address-search?q=…`, signed-in users only), which calls Mapbox Geocoding v6 (`/search/geocode/v6/forward`, limited to the Philippines by default) and returns just street, city, province, postal code and country. The token never reaches the browser. Picking a suggestion fills the form; typing by hand always still works.
- Token: put `MAPBOX_TOKEN=pk.…` in `.env`, or paste it once under **Admin → API health → Mapbox** (it is tested before it is saved and never shown again). A free public token (starts with `pk.`) comes from [account.mapbox.com](https://account.mapbox.com/access-tokens/). Without a token the address form has no suggestions and nothing else changes.
- **Pin your location:** checkout and *My addresses* also show a map (Leaflet + OpenStreetMap). Click it, drag the pin, or press *Use my current location* and the server asks Mapbox (`GET /address-reverse`, reverse geocoding) which address is there and fills the form. Without a Mapbox token (or if Mapbox is down) the address comes from OpenStreetMap's free Nominatim lookup instead, so the form always fills in.
- Errors (bad token, rate limit, offline) are recorded on the API health page and the form falls back to manual entry.

### Openverse — `velora/services/openverse.py` (automatic product photos, no key)
- `start.bat` / `start.sh` run `fill-photos`, and Seller studio → Products has **Fill missing & broken photos**. Both give every product without a working photo a matching one from the internet: Pexels if you added a key, otherwise [Openverse](https://api.openverse.org) (free openly licensed photos, no account). Photos are downloaded through Openverse's own thumbnail endpoint only, re-encoded, stored locally, and their licence credit is saved. If you are offline nothing breaks; it simply tries again next start.

### Pexels — `velora/services/pexels.py` (photos for Seller studio → Find photos)
- `GET {PEXELS_BASE_URL}/search?query=…&orientation=portrait` and `GET /photos/{id}` with your free key in the `Authorization` header (free plan: 200 requests/hour). Key from `.env` (`PEXELS_API_KEY`) or pasted once on the Find photos page (it's tested before it's saved and never shown again).
- A photo is chosen **by id**: the server re-fetches its details from Pexels, so nothing from the browser (a URL, a credit) is trusted. Only images from Pexels' own host (`images.pexels.com`, https) can be downloaded, with a size cap; the image is verified, re-encoded to WebP and stored locally.
- Credits ("Photo by … on Pexels") are saved with the photo. Pexels also shows on the admin **API health** page with a test button.
- If Pexels is unreachable the store is unaffected: photos already chosen are local files.

### OpenStreetMap + Leaflet — the "Visit our store" map ad
- The homepage has a store ad with an interactive map (marker, popup with address and hours, "Get directions" links). It uses **Leaflet** (vendored in `velora/static/vendor/leaflet`, no CDN) with free **OpenStreetMap** tiles. No API key. The "© OpenStreetMap contributors" credit is shown on the map.
- Edit the store name, address, hours and map coordinates under **Admin → Store settings**. The same address is used on the Contact page.
- The map loads when you scroll to it. If the tiles can't load (no internet), it shows the plain address card instead. Tiles are fetched by the visitor's browser, so they're not on the *API health* page (it has a note instead).

## 5. Features

**Storefront.** Editorial hero with floating product card. Shop-by-aisle panel. Bento promo grid with a real top review. Featured, new-arrivals scroller, bestseller ranking and recently viewed sections. Newsletter with validation and database persistence. Mega-menu, search, currency picker, account menu, wishlist, bag. Footer with support and policy pages.

**Catalog.** Consistent 4:5 product cards. Filters for aisle, maker, price and stock, applied by AJAX with skeletons and URL history, and still working without JS. Six sort orders, pagination, search across name, description, maker, category and ingredients. Stock labels and sale/new badges. Image gallery, tabs, related products, rating distribution, verified-buyer reviews and staff replies.

**Bag and checkout.**
- Bag and pricing:
  - Session bag for guests, database bag for customers, merged at login.
  - Slide-out drawer with live quantity and remove, plus a free-shipping meter.
  - Discount codes: percent or fixed, minimum spend, usage limits counted atomically, start and end dates.
  - Configurable flat shipping and free-shipping threshold.
- Placing the order:
  - **Delivery address on every purchase:** the customer picks one of their saved addresses or enters a new one (with an option to save it). Nothing is pre-selected and an order can't be placed without a valid choice; the address is copied onto the order.
  - **Watch options:** size, colour and an optional engraving (see *The collections and the watches*). The server checks every choice and adds the engraving fee itself.
  - **Demo credit:** every buyer starts with ₱500,000 and pays from it at checkout. An order that costs more than the remaining credit is refused (the balance can never go below zero, even with two checkouts at once); cancelling refunds the credit. Paid orders go straight to *Shipped* with a “wait 10 mins” message (`services/payments.py`, built so a real gateway can be plugged in).
  - **One transaction** that re-validates stock, prices and discount on the server, decrements stock with a conditional `UPDATE … WHERE stock >= qty` (so it can't oversell), snapshots item name, SKU, price, discount and image, then records the payment.
  - A one-time checkout token with a unique constraint prevents duplicate orders from double-submits.
  - Confirmation page with an animated check.

**Orders.** Statuses Pending → Confirmed → Processing → Shipped → Delivered, plus Cancelled. Valid transitions are enforced on the server. Cancellation restocks the items and refunds demo payments. Customers see an animated progress tracker and get a notification on every change.

**Animation and UX.**
- Motion:
  - GSAP hero timeline: masked headline lines, photo clip reveal, floating cards, scroll parallax.
  - Staggered `ScrollTrigger.batch` card reveals, hover lift and image zoom.
  - Fly-to-bag add-to-cart with badge bounce, wishlist heart pop with a particle burst.
  - Drawer and dropdown transitions, animated checkout steps, order-tracker timeline.
  - Dashboard bar charts and meters animate in; animated empty states.
- Interface:
  - Toast notifications, confirmation modal for destructive actions, smooth tab ink.
  - Mobile navigation drawer.
  - Loading buttons that block double submission.
  - Smooth dark-mode transition.
- Accessibility and performance:
  - Everything respects `prefers-reduced-motion`.
  - GSAP, Lucide and the fonts (Bricolage Grotesque, Inter) are **self-hosted** in `velora/static/vendor` and `velora/static/fonts`, so the UI also works offline in a VM.

---

## 6. Security

- Passwords: Werkzeug salted hashes (scrypt/pbkdf2). Login lockout after N failures, stored in the database so it holds across workers, plus a per-IP throttle. Session rotation on login. `HttpOnly`/`SameSite=Lax` cookies, `Secure` when `SESSION_COOKIE_SECURE=1`.
- CSRF tokens on every state-changing form and AJAX call (Flask-WTF). Logout is POST-only.
- Server-side role checks. Ownership checks on orders, addresses and notifications (other people's orders return 404). Safe `?next=` redirects only.
- All prices, discounts, stock and totals are recomputed on the server. Browser-supplied amounts are ignored.
- SQLAlchemy ORM and parameterized queries only. Jinja auto-escaping. CSV exports neutralise spreadsheet formulas.
- Uploads: extension allow-list, size limit (`MAX_UPLOAD_MB`), Pillow verification, decompression-bomb guard, **re-encoding to WebP**, which strips metadata and payloads, random filenames, path-traversal-safe serving with its own CSP.
- Headers: a strict Content-Security-Policy (`script-src 'self'`, no inline scripts), `X-Frame-Options: DENY`, `nosniff`, Referrer-Policy, Permissions-Policy.
- Friendly error pages. The debugger is never enabled by default and stack traces never reach customers.
- Audit log covers role and status changes, account disable/enable/unlock, lockouts, product create/update/archive, restocks, category, discount and settings changes, imports, exports and API tests.
- `reset-demo` needs `--yes-delete-everything` and refuses to run in production. `init-db` and `seed` never delete data.

---

## 7. Tests

```bash
python -m pytest -q
```

There are 261 tests. External APIs are mocked, so no network is needed. They cover:
- **Auth and access:** registration, login and lockout, disabled accounts, role permissions and unauthorized admin access, the four distinct dashboards, open redirects, CSRF, health and headers.
- **Catalog and bag:** catalog, search, filters and pagination, cart quantity updates, guest-cart merge, persistent carts, wishlist, newsletter.
- **Checkout and orders:**
  - checkout validation and server-side pricing;
  - discount codes (percent, fixed, minimum, expired, exhausted, usage counting);
  - inventory deduction and re-checks;
  - **duplicate checkout prevention**;
  - failed-payment rollback;
  - order ownership, cancellation rules with restocking, seller status transitions;
  - reviews (purchase required, duplicate blocked, rating range).
- **Integrations:** currency conversion, caching, stale-cache and offline fallback, Open Food Facts parsing, normalization, rate limits, import and offline display.
- **Staff tools and setup:** invalid, oversized and spoofed uploads, path traversal, CSV export, settings, model-photo uploads, cover photos and the bulk loader, database initialization via migrations, and the non-destructive seed.

Useful commands: `python -m flask --app wsgi create-admin`, `python -m flask --app wsgi refresh-rates`, `python -m flask --app wsgi check-images` (checks every remote product photo; broken ones fall back to a local placeholder automatically), `python -m flask --app wsgi db upgrade` / `db migrate`.

---

## 8. Project structure

```
velora/
  __init__.py          app factory, template helpers, error handlers
  config.py            env-driven config (dev / production / testing)
  extensions.py        db, migrate, login manager, CSRF
  models.py            schema (20 tables), order-status rules, settings
  forms.py             Flask-WTF forms + server-side validation
  security.py          role decorator, audit logging, headers, safe redirects
  money.py             Decimal / integer-minor-unit helpers
  seed.py  cli.py      demo data + CLI commands
  services/            cart, pricing, orders, payments, currency, openfoodfacts,
                       catalog, reports, uploads, api_health
  blueprints/          main, catalog, auth, shop, account, seller, admin
  templates/           Jinja2 (storefront, account, seller studio, admin console)
  static/              css/app.css, js/app.js, vendor/ (GSAP, Lucide), fonts/, img/
migrations/            Alembic migration(s)
scripts/               setup/run for Linux (.sh) and Windows (.bat), Gunicorn runner
tests/                 pytest suite
serve.py  wsgi.py      Waitress runner / WSGI entry point
```

---

## 9. Known limitations

- **Payments are simulated** by design (`DemoPaymentProvider`). A real gateway needs a new `PaymentProvider`, webhooks and PCI-compliant hosted fields. Car listings are demo items: a real dealership would take a reservation deposit rather than full checkout.
- **Stock photos** are hot-linked from Unsplash and couldn't be checked from the build sandbox, which had no outbound access to those hosts. Run `python -m flask --app wsgi check-images` in your VM. Any failing image automatically shows the local placeholder. Replace them with your own model photos anytime (see section 1).
- SQLite is fine for a single VM and moderate traffic. With many concurrent writers, move to PostgreSQL by setting `DATABASE_URL`; the code is ORM-only. The per-IP login throttle is per-process, while the per-account lockout is shared through the database.
- No outbound email: notifications are in-app. Password reset by email isn't implemented, but admins can manage accounts.
- Exchange rates are ECB daily reference rates, so they don't move intraday and are for display only.
- Seller accounts share one catalog. This is not an isolated multi-vendor marketplace.

Third-party assets: GSAP (Standard “no charge” license), Lucide (ISC), Bricolage Grotesque and Inter (SIL OFL 1.1), and Open Food Facts data (ODbL). License files are included next to the assets.
