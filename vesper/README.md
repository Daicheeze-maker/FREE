# Vesper — a multi-vendor perfume marketplace (university demo)

A working prototype of a luxury fragrance marketplace: four fictional perfume houses, five scents each,
with a React + TypeScript frontend, a FastAPI + SQLAlchemy + SQLite backend, PayMongo Hosted Checkout
(test mode) and Frankfurter currency conversion.

> All houses, perfumes and prices are **fictional demonstration content**. No real payments are processed.

```
vesper/
├── backend/            FastAPI app, SQLite DB, Pytest suite
│   ├── app/
│   │   ├── main.py             REST endpoints
│   │   ├── models.py           Seller, Product, Customer, Cart, CartItem, Order, OrderItem, Payment, WebhookEvent, Subscriber
│   │   ├── seed.py / seed_data.py   4 sellers × 5 products
│   │   └── services/
│   │       ├── catalog.py      seller/product limits, search/filter/sort
│   │       ├── orders.py       cart, checkout, idempotent paid/failed transitions
│   │       ├── paymongo.py     PayMongo checkout sessions, status check, webhook signatures
│   │       └── currency.py     Frankfurter rates, caching, Decimal conversion
│   ├── tests/          47 tests (+2 live tests, skipped without credentials)
│   └── .env.example
├── frontend/           React 19, TypeScript, Tailwind 4, React Router 7, Motion, Lucide
│   ├── src/pages/      Home, Shop, ProductPage, Houses, CartPage, Checkout, Payment
│   ├── src/lib/        api client, cart/currency store, exact money maths
│   └── e2e/smoke.mjs   Playwright end-to-end run of the full shopping flow
└── TEST_REPORT.md      actual test output
```

## Requirements

- Python 3.11+ (tested on 3.13)
- Node.js 20+ (tested on 22)

## 1. Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                 # defaults to PAYMENT_MODE=mock, works with no keys
python -m app.seed                   # creates vesper.db with 4 sellers / 20 products (use --reset to start over)
uvicorn app.main:app --reload --port 8000
```

The API also creates and seeds the database on first start. Interactive API docs: http://localhost:8000/docs

## 2. Frontend

```bash
cd frontend
npm install
npm run dev                          # http://localhost:5173 (proxies /api to :8000)
```

## 3. Tests

```bash
cd backend && pytest -v              # backend: limits, catalog, cart, checkout, PayMongo, Frankfurter
cd frontend && npm test              # frontend: money maths, quantity selector, form validation
cd frontend && npm run e2e           # full browser flow; needs both servers running, PAYMENT_MODE=mock,
                                     # and Playwright (npm i -D playwright && npx playwright install chromium)
```

Live-API tests are skipped unless you opt in:

```bash
RUN_LIVE_API_TESTS=1 pytest tests/test_currency.py::test_live_frankfurter
PAYMONGO_LIVE_TEST_KEY=sk_test_... pytest tests/test_payments.py::test_live_sandbox_checkout_session
```

## Configuring the API keys securely

All secrets live in `backend/.env` (git-ignored). The browser only calls `/api/...` on our own backend, so
no key ever reaches frontend code.

**PayMongo (test mode)**
1. Create a PayMongo account and switch the dashboard to **test mode**.
2. Copy the **test secret key** (`sk_test_...`) into `PAYMONGO_SECRET_KEY`. Live keys (`sk_live_...`) are
   refused by the code.
3. Create a webhook pointing to `https://<your-public-url>/api/webhooks/paymongo` for the events
   `checkout_session.payment.paid` and `payment.failed`, and put its secret in `PAYMONGO_WEBHOOK_SECRET`.
   For local development, expose port 8000 with a tunnel (e.g. ngrok or cloudflared).
4. Set `PAYMENT_MODE=paymongo` and restart the backend. Pay using PayMongo's published test cards / test
   e-wallet flow.

**Frankfurter** needs no key. Set `FRANKFURTER_BASE_URL` only if you self-host it.

## How the important parts work

**Limits (enforced in Python).** `services/catalog.py` rejects a 5th seller and a 6th product per seller with
HTTP 409. The seed script goes through the same functions. Admin creation endpoints exist at
`POST /api/admin/sellers` and `/api/admin/products` (need `X-Admin-Token`) to demonstrate this.

**Money.** All prices are stored as integer PHP centavos. Totals are computed on the server from database
prices; anything the client sends as a price is ignored. Shipping is a flat ₱180 **demo rate**.

**Payment flow (PayMongo).**
1. `POST /api/checkout` re-checks stock, computes totals, stores a `pending` order and creates a PayMongo
   checkout session with server-side line items (in PHP).
2. The shopper is redirected to PayMongo's hosted page.
3. On return to `/order/:id?result=success`, the frontend calls `POST /api/orders/:id/verify`. The
   backend **asks PayMongo** for the session's payment status. The redirect alone never marks an order as paid.
4. The webhook (HMAC-SHA256 signature checked, replays older than 5 minutes rejected, live-mode events
   rejected) is a second confirmation path. Event ids are stored, so redeliveries do nothing.
5. `mark_paid` uses a conditional `UPDATE ... WHERE status IN ('pending','failed')`. Only the first
   confirmation deducts stock (with `stock >= qty` guards) and empties the cart, so verify + webhook +
   retries can't double-deduct.

**Mock payment mode.** With `PAYMENT_MODE=mock` (the default), checkout redirects to a local page that is
clearly labelled *"Mock payment gateway · demo only"*, where you choose success or failure. It uses the same
`mark_paid` / `mark_failed` code, and the endpoint is disabled when `PAYMENT_MODE=paymongo`.

**Currency (Frankfurter).** `GET /api/currency/rate?to=USD` fetches `GET {FRANKFURTER_BASE_URL}/rates?base=PHP&quotes=USD`
(it also accepts the v1 `/latest` response shape), caches it for 6 hours, serves the last good rate (marked
stale) if a refresh fails, and returns 503 if no rate has ever been fetched. The frontend then shows prices
in PHP with a notice. Conversion uses `Decimal` with half-up rounding on the server, and the same
integer/BigInt maths in the browser, so both agree to the cent. Checkout is always charged in PHP.

## Product images

This environment had no access to image hosts, so product "photography" is rendered as art-directed SVG
bottles. Each house has its own glass silhouette and each scent its own colour, shown in studio, evening and
label-detail views (`src/components/Bottle.tsx`). To use real photos, add them to `frontend/public/` and
swap that component.
