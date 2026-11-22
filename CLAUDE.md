# CLAUDE.md — project memory

Read this first. It is the running memory of how this project was built and what its owner wants.
Keep it up to date: add to the **Change log** and **Decisions** when something changes.

## What this is

**Aurelune** (Python package name: `velora`), a demo e-commerce store for a school activity. It sells **only watches**.
Flask + SQLAlchemy + Alembic, SQLite by default, Waitress server, GSAP animations, no build step.

- Repo: `Daicheeze-maker/FREE`, working branch `claude/eloquent-archimedes-lakibj`. The owner pulls this branch onto
  Windows school PCs and runs it there; a zip (`velora-market.zip`, `git archive` of HEAD) is also sent each time.
- The store name comes from `STORE_NAME` in `.env` (default "Aurelune"), injected into templates as `brand`.

## How the owner runs it (Windows school PCs)

- Double-click **`start.bat`**: first run sets up `.venv`; every run does `init-db`, `seed`, `upgrade-demo`, `fill-photos`,
  then serves on http://127.0.0.1:5000 and opens the browser. `start.sh` is the Linux/macOS twin.
- **Device Guard** blocks `.venv\Scripts\*.exe` (flask.exe, pip.exe). Always use `python -m flask …` / `python -m pip …`.
- PowerShell blocks `Activate.ps1`. Give the owner `.bat` files to double-click (e.g. `create-admin.bat`) or Command Prompt steps.
- `*.bat` files must keep **CRLF** line endings (`.gitattributes`). Python `open().write()` in text mode turns them into LF: write
  them with `newline=''`.
- To update: just double-click `start.bat`: it runs `git pull --ff-only` on the branch first, then **restarts itself**
  (`"%~f0" --updated`) because Windows reads a running .bat from disk; it prints `Store version: <hash> (<date>)`. Ask the owner
  for that line when something looks old. Manual: `git pull origin claude/eloquent-archimedes-lakibj`.

## Accounts and roles

- **No demo accounts.** People register on the site; `start.bat`/`upgrade-demo` deletes the old sample accounts
  (`buyer1/buyer2/admin@velora.example` + `#seller` profiles) unless they have a real (non-`seed-`) order.
- Register asks **Shop or Sell**. Every buyer gets a linked seller profile (email + `#seller`, `SELLER_SUFFIX`);
  "Sell" signs straight into the seller profile and opens Seller studio. Switch profiles from the account menu / sidebar.
- Login checks the real password (no auto-registration).
- **Easiest for the owner:** start the store, Sign in page → **Set up the admin account** (one-time page).
- Admins are also made with `create-admin.bat` (double-click) / `python -m flask --app wsgi create-admin`, or by `start.bat`
  (`flask ensure-admin`) when `ADMIN_EMAIL` and `ADMIN_PASSWORD` are set in the local `.env` (gitignored, stays on the PC).
  Never put a real password or the owner's login in the repository; `ensure-admin` never resets an existing admin's password.
- Each buyer starts with **₱500,000 demo credit** (`STARTING_CREDIT_MINOR`), spent at checkout with an atomic UPDATE.
- Admin → **Active sellers** (`/admin/sellers`) lists seller profiles and their last sign-in (active = last 30 days).

## Catalog: watches with options

- 6 collections: Dress Watches, Dive Watches, Chronographs, Field & Pilot, Smart Watches, Ladies Watches. 20 watches (`velora/seed.py` `PRODUCTS`). Nothing is sold out in a fresh store.
- **Spectrum Chronograph** (Chronographs): 10 colour editions (Black, White, Blue, Red, Green, Purple, Pink, Orange, Yellow, Teal),
  cut from the owner's grid image. One photo per colour (`static/img/watches/spectrum-<colour>.webp`) and a **drag-to-turn 360° view**.
- Every watch has **case sizes** (`Product.sizes`), **colours** (`Product.colors`) and optional **engraving**
  (`engraving_fee_minor`, None = not offered; `engraving_max` chars, default 20).
- A cart line is keyed by `"size|colour|engraving"`, stored in the (historically named) `size` column of `CartItem`;
  `OrderItem.size` stores the human label ("42 mm · Blue · Engraved “MJ”"). Helpers: `velora/services/cart.py`
  (`make_key`, `split_key`, `clean_size` validates everything, `CartLine.unit_price_minor` adds the engraving fee server-side).
- Stock is shared by all variants of a watch.
- `refresh_catalog()` (run by `upgrade-demo` when `demo_status()` says `stale`) converts any older store (fashion, shoes, bags…)
  into the watch store **without** touching accounts, orders, settings or uploads. It is idempotent.

## Photos

- **The store's own photos** come from the owner's Google Drive folder
  (https://drive.google.com/drive/folders/1LeR_NbqxLa181UPOy0WyuAwNDTxm9b0d). They are converted to WebP and committed in
  `velora/static/img/watches/`, mapped to watches in `seed.OWN_PHOTOS` (several angles each) and to homepage/sign-in
  spots in `photos.DEFAULT_SLOT_FILES`. They always load, even offline. `refresh_catalog` swaps stock photos for them but
  never replaces a photo a seller uploaded.
- Watches without an own photo use Unsplash links with a fallback chain (`seed.alt_next()` → `data-photo-alts` on `<body>` →
  `app.js` `recover()`), ending on a known-good photo, then a local placeholder.
- `fill-photos` / Products → "Fill missing & broken photos": Pexels if a key is set, otherwise Openverse (no key).
- To add more own photos: put them in the Drive folder, download, convert to WebP in `velora/static/img/watches/`,
  add to `OWN_PHOTOS`, run tests.

## 360° view

- `velora/spin.py` `spin_data(product)` finds frames in `velora/static/img/spin/<product-slug>/<colour-slug>/01.webp…` (turning
  order). A colour's main photo is the product image ending in `-<colour-slug>.webp`. Nothing else to configure: drop frames
  in a folder like that and the product page shows the **360° View** button.
- `static/js/spin.js`: pointer drag (mouse/touch/pen) with a short glide, cross-fade between frames, arrow keys/Home/Escape,
  a small automatic half-turn on open (skipped with reduced motion), colour buttons and colour thumbnails switch photo + frames.
- Spectrum's 6 frames per colour = front, 3/4, side, back from the image + mirrored side and 3/4. They come from ~70 px
  thumbnails, so they are soft; better frames (e.g. 24–36 photos per turn) can replace them file for file.

## Address, map and external services

- Checkout and My addresses: **Pin your location** map (Leaflet + OSM tiles, vendored). Pin → `/address-reverse`
  (Mapbox if `MAPBOX_TOKEN`/admin token, else OSM Nominatim), with browser-side fallbacks (Nominatim, BigDataCloud) in
  `static/js/pin-map.js` (CSP `connect-src` allows those two hosts). Typing suggestions need a Mapbox token.
- APIs: Open Food Facts (import tool, kept from the original brief), Frankfurter (display currency), Pexels, Openverse,
  Mapbox, Nominatim, OpenStreetMap tiles. All optional; the store works offline.

## Owner preferences (keep following these)

- Plain, friendly explanations; the owner is a student, often on a school PC. Give exact click/double-click steps.
- Test everything before handing over (pytest + a real-browser check with Playwright). Be honest about what could not be checked
  (the cloud sandbox can't reach most image hosts).
- Always push to the branch and send the updated zip.
- Top menu is hidden on collection pages (left "Collections" list is used there). Back button on every page except home,
  sign-in, register and checkout.

## Tests

`python -m pytest -q` (about 261 tests, ~3½ min; external APIs are faked). `tests/conftest.py`: `seed(demo_accounts=True)`
creates sample people only for tests; `in_stock_product()` switches off a watch's options so tests can add it plainly;
`optioned_product()` is a normal watch with options.

## Change log (newest last)

1. Built the fashion store (4 roles, OFF + Frankfurter, demo payment, GSAP), 2 buyers + 2 sellers, sizes, ₱500K credit, map ad.
2. Pexels photos, Shoes/Accessories collections, non-destructive catalog refresh.
3. Removed demo accounts; Mapbox address search; hid top menu on shop pages; back buttons; Shop/Sell at registration;
   admin Active sellers; renamed store to Aurelune; keyless photo fill (Openverse); pin-to-autofill with OSM fallbacks.
4. **Pivot to a watch-only store** with size / colour / engraving on every watch; automatic conversion of old stores;
   fixed photo fallback race and always-visible option errors.
5. Shop images now come from the owner's Google Drive folder (committed in `velora/static/img/watches/`); memory moved to this
   file in the GitHub repo (the owner first asked for an Obsidian vault named CLAUDE, then chose GitHub).

6. Added the **Spectrum Chronograph** in 10 colours from the owner's image, with a drag-to-turn 360° view.
7. Removed the sold-out Crystal Bezel Watch (`seed.REMOVED_SLUGS`). Fixed wrong stock photos: one Unsplash link was a shoe,
   and the Smart Fitness Watch showed an analog watch (`seed.WRONG_PHOTO_IDS` / `WRONG_PHOTO_ON`; `refresh_catalog` repairs
   existing stores). Verified-on-screen smartwatch photos: `SW1`, `SW2` in `seed.py`.
8. Fixed `demo_status()`: a store with a seller-made watch was never marked stale, so new demo watches (Spectrum) were not added.
9. The owner's PC kept showing the removed shoe-photo watch because it had an old copy. Now `start.bat`/`start.sh` update
   themselves; `visible_products()` and the product page hide `REMOVED_SLUGS` even if an old database still has them; the
   homepage (New arrivals, Featured, hero card) only shows in-stock watches.
10. `flask ensure-admin`, run by start.bat: creates the admin from `ADMIN_EMAIL`/`ADMIN_PASSWORD` in the local `.env`.
11. Double-clicking `create-admin.bat` did nothing on the owner's PC. Added a one-time **Set up the admin account** page
    (`/account/setup-admin`, linked from the sign-in page): only while the store has no admin, only from 127.0.0.1 (no
    X-Forwarded-For). `create-admin.bat` now always stays open and says what happened.

## Open items / ideas

- Stock photos the owner has seen that only roughly match: Rose Gold Bracelet Watch shows a black-dial men's watch, Petite
  Mesh Watch shows a leather-strap chronograph. Replace them with the owner's own photos when available.

- Spectrum's 360° frames are low resolution (cut from small thumbnails); replace with real photos for a sharper turn.

- 10 watches still use stock photos (Moonphase, Deep Blue Titanium, Explorer, the 3 smart watches, the 4 ladies' watches):
  add photos for them to the Drive folder and map them in `OWN_PHOTOS`.
- Several Drive photos show real brand logos (Rolex, Patek Philippe, Panerai, De Bethune) on watches the store sells under
  invented brand names; fine for a class demo, not for a real shop.
