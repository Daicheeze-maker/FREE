# Live demo script (about 12 minutes)

A walkthrough for the final presentation, in an order that covers every rubric criterion. Do the **Before the demo**
part at home, so the live part is just clicking and showing.

## Before the demo (once, at home)

1. Create the VM (VirtualBox, Ubuntu 24.04 LTS, **2 CPUs, 4096 MB RAM, 25 GB disk**, NAT) and add the port-forwarding
   rule: TCP, Host Port 5000 → Guest Port 5000. Full steps: `docs/aurelune-process-flow.pdf`, pages 6–7, or README §2.
2. In the VM, in the store folder: `bash scripts/vm-setup.sh` (installs everything and the `aurelune` service).
3. Open http://127.0.0.1:5000 → **Sign in → Set up the admin account**.
4. Create a **buyer** account (Create account) and a second buyer who applies to sell (*Sell on Aurelune*). Approve the
   seller at **Admin → Seller requests**.
5. Optional: add a free Mapbox token at **Admin → API health** for address suggestions.
6. Restart the VM once and run `bash scripts/vm-check.sh`: it should end with **VM CHECK: everything is OK.**

## Live demo

| # | Time | Show | Say / point out | Rubric |
|---|---|---|---|---|
| 1 | 1 min | VirtualBox window: the VM's **Settings → System / Network** | 2 CPUs, 4 GB RAM, NAT with port forwarding 5000 → 5000 | PlatTech: VM provisioning; localhost & network |
| 2 | 1.5 min | In the VM terminal: `bash scripts/vm-check.sh` | Resources, isolated `.venv`, no package conflicts, database integrity + foreign keys, service running, listening on 0.0.0.0:5000, every page 200, **no errors in the log** | PlatTech: verification, service reliability; IPT: VM & localhost |
| 3 | 0.5 min | `sudo systemctl status aurelune` | Starts at boot, restarts by itself if it stops (`Restart=on-failure`) | PlatTech: service & database reliability |
| 4 | 3 min | **On your own PC's browser** (through port forwarding) http://127.0.0.1:5000: Shop ▾ → a collection → search "blue" → open a watch → **360° View** drag → pick size, colour, engraving → Add to bag → bag drawer | Search and filters, options validated on the server, stock shared by all options | IPT: core e-commerce; UI/UX |
| 5 | 2 min | Checkout as the buyer: phone with country picker, **Pin your location** on the map (fills the address), place order → confirmation → **My account → Orders** | Map pin uses **Mapbox / OpenStreetMap Nominatim**; payment uses ₱500,000 demo credit; order history | IPT: checkout, order history, outside API |
| 6 | 0.5 min | Header **PHP** button → USD | Prices converted with **Frankfurter** (European Central Bank rates); orders still charged in PHP | IPT: outside API |
| 7 | 1 min | Edge cases: set a watch's stock to 0 in Seller studio → its page says Sold out, Add to bag is off; an empty bag says so; checkout with an empty bag sends you back | Graceful handling, no crashes | IPT: edge cases; PlatTech: error-free |
| 8 | 1.5 min | http://127.0.0.1:5000/api/docs, then in the VM terminal the curl commands from `docs/API.md` (health → products → token → add to bag → place order) | Own REST API: methods, JSON, status codes 201/401/409/422; `Idempotency-Key` stops double orders | IPT: API integration & design |
| 9 | 0.5 min | Admin → **Seller requests**, **API health** (Test buttons) | Sellers by approval only; outside APIs monitored | IPT: core features |
| 10 | 0.5 min | Show `README.md`, `requirements.txt`, `docs/API.md` | Setup docs, pinned packages, endpoint list | IPT: documentation; PlatTech: documentation |

## If something goes wrong during the demo

| Problem | Quick fix |
|---|---|
| The page doesn't open on your PC | In the VM: `bash scripts/vm-check.sh`. If it says "Listening on 127.0.0.1", the `.env` needs `HOST=0.0.0.0`: run `bash scripts/vm-setup.sh` again |
| "Port 5000 is already in use" | The service is already running: just open the page. Or `sudo systemctl restart aurelune` |
| Service not running | `sudo systemctl restart aurelune`, then `journalctl -u aurelune -n 50` to see why |
| Currency or map lookup says unavailable | The VM has no internet right now; everything else keeps working. Show **Admin → API health** |

## What each rubric criterion maps to

| Criterion | Where it is in the project |
|---|---|
| Core e-commerce (IPT) | Accounts and sign-in (`blueprints/auth.py`), catalog/search (`services/catalog.py`), bag (`services/cart.py`), checkout + orders (`services/orders.py`), order history (`/account/orders`). Edge cases tested in `tests/` (sold out, empty bag, not enough credit, double submit) |
| API integration & design (IPT) | Own REST API `blueprints/api.py` + `docs/API.md`; outside APIs Frankfurter (`services/currency.py`), Mapbox (`services/mapbox.py`), Nominatim (`services/nominatim.py`), all with timeouts and fallbacks; `tests/test_rest_api.py` |
| Python back-end & database (IPT) | Flask app factory + blueprints (MVC: `models.py`, `templates/`, `blueprints/`), SQLAlchemy models with foreign keys and constraints, Alembic migrations, hashed passwords (`werkzeug.security`), WTForms + API validation |
| VM & localhost (IPT), localhost & network (PlatTech) | `scripts/vm-setup.sh`, `.env` `HOST=0.0.0.0`, VirtualBox port forwarding, `serve.py` port-conflict message |
| Error-free execution (PlatTech) | `tests/test_no_broken_pages.py` opens every link as visitor, buyer, seller and admin (no 404/500); 330+ automated tests |
| VM provisioning (PlatTech) | Resources in the VM settings; `.venv`; pinned `requirements.txt`; `.env`; `flask doctor` checks for missing modules |
| Service & database reliability (PlatTech) | `deploy/aurelune.service` (systemd, auto-restart), Waitress with 8 threads, SQLite WAL + busy timeout, `/healthz` and `/api/v1/health` |
| Verification & documentation (both) | `scripts/vm-check.sh`, `README.md`, `docs/API.md`, this file, `docs/aurelune-process-flow.pdf` |
