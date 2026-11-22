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
- **Selling is by application (marketplace style).** Everyone registers as a buyer. Register's **Sell** choice (or account
  menu → *Sell on Aurelune*, or My account → *Sell*) opens `/account/sell`: shop name, phone, what they'll sell. Only an admin
  decides, at **Admin → Seller requests** (`/admin/seller-requests`, badge with the pending count). Approval creates the
  linked seller profile (email + `#seller`, `SELLER_SUFFIX`, named after the shop); rejection sends the admin's note and they can
  re-apply. Admin → Active sellers can **Remove seller access**. Logic: `velora/services/sellers.py`; model `SellerApplication`.
  `User.linked_profile` only returns switched-on profiles. Seller profiles from older versions were kept as they are.
- Login checks the real password (no auto-registration).
- **Easiest for the owner:** start the store, Sign in page → **Set up the admin account** (one-time page).
- Admins are also made with `create-admin.bat` (double-click) / `python -m flask --app wsgi create-admin`, or by `start.bat`
  (`flask ensure-admin`) when `ADMIN_EMAIL` and `ADMIN_PASSWORD` are set in the local `.env` (gitignored, stays on the PC).
  Never put a real password or the owner's login in the repository; `ensure-admin` never resets an existing admin's password.
- Each buyer starts with **₱500,000 demo credit** (`STARTING_CREDIT_MINOR`), spent at checkout with an atomic UPDATE.
- Admin → **Active sellers** (`/admin/sellers`) lists seller profiles and their last sign-in (active = last 30 days).

## Catalog: watches with options

- 6 collections: Dress Watches, Dive Watches, Chronographs, Field & Pilot, Smart Watches, Ladies Watches. **60 watches**, 10 per
  collection, all from `velora/catalog_more.py` (`seed.PRODUCTS` is built from it). Nothing is sold out in a fresh store.
- **Only generated photos** (owner's wish, for a consistent, clean look). The first 20 watches (`seed._OLD`) and the Spectrum
  Chronograph are in `seed.REMOVED_SLUGS`: start-up deletes them from older stores (order history keeps its snapshots) and
  features the 2 best sellers per collection if nothing is featured. Watches a seller added are kept.
- Every watch has **case sizes** (`Product.sizes`), **colours** (`Product.colors`) and optional **engraving**
  (`engraving_fee_minor`, None = not offered; `engraving_max` chars, default 20).
- A cart line is keyed by `"size|colour|engraving"`, stored in the (historically named) `size` column of `CartItem`;
  `OrderItem.size` stores the human label ("42 mm · Blue · Engraved “MJ”"). Helpers: `velora/services/cart.py`
  (`make_key`, `split_key`, `clean_size` validates everything, `CartLine.unit_price_minor` adds the engraving fee server-side).
- Stock is shared by all variants of a watch.
- `refresh_catalog()` (run by `upgrade-demo` when `demo_status()` says `stale`) converts any older store (fashion, shoes, bags…)
  into the watch store **without** touching accounts, orders, settings or uploads. It is idempotent.

## Photos

- Every product photo and the homepage/sign-in spots (`photos.DEFAULT_SLOT_FILES`) are the generated photos in
  `velora/static/img/watches/` (mapped by `seed.OWN_PHOTOS`); they always load, even offline. The owner's Google Drive photos
  and the Spectrum images were removed (still in git history before this change if ever wanted back).
- `fill-photos` / Products → "Fill missing & broken photos" (Pexels if a key is set, else Openverse) only fills watches
  that have no working photo, e.g. one a seller added.

## Generated watch photos (the 60 in `catalog_more.py`)

- Made with **Gemini (`gemini-3.1-flash-image`) through the Figma MCP** (`generate_image`, owner's Figma student team,
  file "Aurelune watch photos"). Canva's generator only returned 200 px previews; Higgsfield had no credits.
- One image per watch: an **8-angle turntable sheet** (2 rows × 4 tiles, 45° steps: front, front-right, right, back-right,
  back, back-left, left, front-left). One sheet keeps the watch identical across views (separate calls don't).
- Sliced into `static/img/spin/<slug>/<colour>/01…08.webp` (360° frames) and `static/img/watches/<slug>-<colour>.webp`
  (main photo = front tile on a 4:5 canvas). Download host `www.figma.com` was added to the "FREE" cloud environment.
- Each new watch has one colour (the one in its photo), two case sizes, and engraving except most smart watches.

## 360° view

- `velora/spin.py` `spin_data(product)` finds frames in `velora/static/img/spin/<product-slug>/<colour-slug>/01.webp…` (turning
  order). A colour's main photo is the product image ending in `-<colour-slug>.webp`. Nothing else to configure: drop frames
  in a folder like that and the product page shows the **360° View** button.
- `static/js/spin.js`: pointer drag (mouse/touch/pen) with a short glide, cross-fade between frames, arrow keys/Home/Escape,
  a small automatic half-turn on open (skipped with reduced motion), colour buttons and colour thumbnails switch photo + frames.
- Frames fill the viewer (`object-fit: cover`); watches in `spin.SOFT_FRAMES` (now empty) would be shown smaller. Between frames a
  short fade happens around the middle of each step (no long see-through double image).

## Phone numbers

- `velora/phones.py` with the free **`phonenumbers`** package (Google libphonenumber rules, offline, in requirements.txt).
  Countries = the display currencies' countries: PH, US, GB, JP, SG, AU + euro DE, FR, IT, ES, NL, IE.
- **Mobile numbers only** (delivery updates). Limits come from the metadata: PH = 10 digits after +63 (11 typed with the 0),
  SG 8, AU 9 (+0), etc. Stored as E.164 (`+639171234567`), shown with the `|phone` filter (`+63 917 123 4567`).
- Forms with a phone use `PhoneFormMixin` (`phone` + `phone_country` select, `set_phone()` to prefill a saved number);
  templates use the `phone_field(f, country)` macro; `app.js` keeps digits only and caps them per country (no `maxlength`
  attribute, so pasted "+63 …" isn't cut short). The country defaults to the display currency's country.

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
- Header: logo left; centre menu = **Shop ▾** (mega menu with the 6 collections, each with a
  watch-photo thumbnail from `static/img/collections/<slug>.webp`, cropped from the generated photos, + See all), New arrivals, Best sellers;
  search, currency, theme, account, bag on the right (owner found 6 links too crowded).
- Top menu is hidden on collection pages (left "Collections" list is used there). Back button on every page except home,
  sign-in, register and checkout.

## Tests

`python -m pytest -q` (about 304 tests, ~3½ min; external APIs are faked). `tests/conftest.py`: `seed(demo_accounts=True)`
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
12. **Seller applications:** no more automatic seller profiles; buyers apply, the admin approves/rejects (owner's idea).
13. **Phone numbers per country** (country picker, digit limits, libphonenumber validation, E.164 storage).
15. **60 more watches** with Gemini-generated photos and 8-frame 360° views (see "Generated watch photos"); `slugify`
    now turns accents into plain letters (Étoile → etoile).
16. **Only the generated watches remain** (owner: "remove every product/image that's not from what you made"): the first 20
    watches, the Spectrum Chronograph and the Drive photos are gone; homepage/sign-in photos are generated ones.
17. Calmer header: the six collection links moved into a Shop ▾ menu; logo moved to the left.
18. Shop menu icons replaced by real watch thumbnails (owner: line icons looked unprofessional).
14. The owner starts the store with `.\scripts\run.bat` too: it crashed after a pull added `phonenumbers` because only
    start.bat installed requirements. **Every** start script (start.bat/.sh, scripts/run.bat/.sh) now runs
    `python -m pip install -r requirements.txt`. When adding a package, remember the owner's PC needs it installed.

## Open items / ideas

- Each generated watch has one colour and 8 frames per turn; a few frames show small inconsistencies (AI images).
