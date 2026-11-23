# Aurelune REST API (v1)

The store has its own JSON REST API at **`/api/v1`**, next to the website. The same list is in the running store at
**http://127.0.0.1:5000/api/docs** (a page) and **http://127.0.0.1:5000/api/v1** (JSON).

- **Format:** JSON in, JSON out. Send bodies with `Content-Type: application/json`.
- **Sign-in:** `POST /api/v1/auth/token` returns a token. Send it as `Authorization: Bearer <token>`.
  Tokens last 24 hours (`API_TOKEN_HOURS` in `.env`). Changing the account's password signs every token out.
  The API never uses the website's login cookie, so it needs no CSRF token and can't be triggered from another site.
- **Money:** always Philippine pesos, as `{"minor": 1590000, "formatted": "₱15,900.00"}` (minor = centavos).
- **Lists:** `{"items": [...], "page": 1, "per_page": 20, "total": 60, "pages": 3}`. Use `?page=` and `?per_page=` (max 50).
- **Code:** `velora/blueprints/api.py`. **Tests:** `tests/test_rest_api.py`.

## Status codes

| Code | When |
|---|---|
| 200 OK | Read or change succeeded |
| 201 Created | A product, bag line or order was created (`Location` header points to it) |
| 204 No Content | Deleted or emptied |
| 400 Bad Request | Broken JSON, or a query parameter that isn't a number / allowed value |
| 401 Unauthorized | No token, or the token is wrong or expired (`WWW-Authenticate: Bearer`) |
| 403 Forbidden | Signed in, but this account's role can't do it (e.g. a buyer creating products) |
| 404 Not Found | No such product, order, bag line or route (someone else's order also answers 404) |
| 405 Method Not Allowed | Wrong HTTP method for that path |
| 409 Conflict | Sold out, not enough stock or demo credit, empty bag, or an order step that isn't allowed |
| 415 Unsupported Media Type | A body that isn't JSON |
| 422 Unprocessable Entity | A field needs fixing; `fields` says which |
| 429 Too Many Requests | Too many sign-in attempts (`Retry-After` header) |
| 502 / 504 | An outside service failed / took too long (timeout) |
| 503 Service Unavailable | Exchange rates unavailable and none saved yet (`Retry-After`) |

Every error has the same shape:

```json
{"error": {"status": 422, "code": "validation_failed", "message": "Some fields need fixing.",
           "fields": {"price": "Must be more than 0.", "category": "Use a collection slug from GET /api/v1/categories."}}}
```

## Endpoints

| Method | Path | Who | What it does |
|---|---|---|---|
| GET | `/api/v1` | anyone | This list of endpoints |
| GET | `/api/v1/health` | anyone | Server, database and outside-API status |
| POST | `/api/v1/auth/token` | anyone | Sign in with email and password; returns a Bearer token |
| GET | `/api/v1/me` | signed in | The signed-in account (role, demo credit) |
| GET | `/api/v1/categories` | anyone | The 6 collections with product counts |
| GET | `/api/v1/products` | anyone | Search and list watches: `q`, `category`, `brand`, `min_price`, `max_price`, `in_stock=1`, `sort` (featured, newest, popular, price_asc, price_desc, rating), `page`, `per_page` |
| GET | `/api/v1/products/<id or slug>` | anyone | One watch with sizes, colours, engraving, stock and photos |
| POST | `/api/v1/products` | seller, admin | Create a watch |
| PATCH | `/api/v1/products/<id>` | seller, admin | Change some fields of a watch |
| DELETE | `/api/v1/products/<id>` | seller, admin | Archive a watch (kept for order history) |
| GET | `/api/v1/cart` | buyer | The bag with prices, totals and any stock problems |
| POST | `/api/v1/cart/items` | buyer | Add a watch: `product_id`, `quantity`, `size`, `color`, `engraving` |
| PATCH | `/api/v1/cart/items/<id>` | buyer | Change a bag line's quantity (0 removes it) |
| DELETE | `/api/v1/cart/items/<id>` | buyer | Remove one bag line |
| DELETE | `/api/v1/cart` | buyer | Empty the bag |
| GET | `/api/v1/orders` | signed in | Your orders, newest first (seller/admin: every order; filter with `status`) |
| POST | `/api/v1/orders` | buyer | Place an order from the bag, paid with demo credit |
| GET | `/api/v1/orders/<number>` | owner, seller, admin | One order with items, delivery address and payment |
| PATCH | `/api/v1/orders/<number>` | seller, admin | Move an order to its next status, e.g. `{"status": "delivered"}` |
| POST | `/api/v1/orders/<number>/cancel` | owner | Cancel while the order is still pending or confirmed |
| GET | `/api/v1/rates` | anyone | Display-currency rates (**outside API: Frankfurter / ECB**) |
| GET | `/api/v1/geocode/reverse?lat=&lng=` | signed in | Map pin to street address (**outside API: Mapbox, else OpenStreetMap Nominatim**) |

## Outside APIs (integrated, with error and timeout handling)

| Outside API | Used for | Through this API | If it fails |
|---|---|---|---|
| **Frankfurter** (`api.frankfurter.dev`, European Central Bank rates) | Prices in USD, EUR, GBP, JPY, SGD, AUD | `GET /api/v1/rates` | Saved rates are reused (marked `stale`); with none saved: 503 + `Retry-After`. Waits `API_RETRY_BACKOFF_MINUTES` before asking again |
| **Mapbox Geocoding** (`api.mapbox.com`, free token) | Address suggestions and pin-to-address | `GET /api/v1/geocode/reverse` | Falls back to Nominatim |
| **OpenStreetMap Nominatim** (`nominatim.openstreetmap.org`) | Pin-to-address without a token | `GET /api/v1/geocode/reverse` | 504 on timeout, 502 if down; the address can still be typed |
| OpenStreetMap tiles, Pexels, Openverse, Open Food Facts | Map pictures, product photos, import tool | (website only) | Each feature shows "unavailable" |

Every outside call has a timeout (`HTTP_TIMEOUT`, default 8 seconds) and its last success/error is shown on
**Admin → API health** and in `GET /api/v1/health`.

## Try it (Ubuntu VM terminal)

Replace the email and password with an account you created on the site. `jq` is optional (`sudo apt install jq`)
and only makes the output easier to read.

```bash
curl -s http://127.0.0.1:5000/api/v1/health | jq
```
```bash
curl -s "http://127.0.0.1:5000/api/v1/products?category=dive-watches&per_page=3&sort=price_asc" | jq
```
```bash
TOKEN=$(curl -s -X POST http://127.0.0.1:5000/api/v1/auth/token -H "Content-Type: application/json" \
  -d '{"email":"buyer@example.com","password":"YourPassword1"}' | jq -r .token)
```
```bash
curl -s -X POST http://127.0.0.1:5000/api/v1/cart/items -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" -d '{"product_id": 22, "quantity": 1, "size": "41 mm", "color": "Blue", "engraving": "MJ"}' | jq
```
```bash
curl -s -X POST http://127.0.0.1:5000/api/v1/orders -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -H "Idempotency-Key: demo-1" -d '{"address": {"full_name": "Juan Dela Cruz", "phone": "09171234567", "phone_country": "PH",
  "line1": "12 Rizal St", "city": "Naga City", "region": "Camarines Sur", "postal_code": "4400"}}' | jq
```
```bash
curl -s http://127.0.0.1:5000/api/v1/rates | jq
```

(Product 22 is Riviera Blue Chrono 41 in a fresh store; use `GET /api/v1/products` to see ids.)
Sending the same `Idempotency-Key` again returns the same order (200) instead of buying twice.

## Example responses

`POST /api/v1/auth/token` → **200**

```json
{"token": "eyJ1aWQiOjV9.Zx...", "token_type": "Bearer", "expires_in": 86400,
 "user": {"id": 5, "email": "buyer@example.com", "name": "Juan", "role": "customer",
          "demo_credit": {"minor": 50000000, "formatted": "₱500,000.00"}}}
```

`POST /api/v1/cart/items` with a watch that is sold out → **409**

```json
{"error": {"status": 409, "code": "out_of_stock", "message": "Abyss 300 Black is sold out."}}
```

`PATCH /api/v1/orders/VM-2611-AB12` as a seller with `{"status": "pending"}` on a shipped order → **409**

```json
{"error": {"status": 409, "code": "invalid_transition", "message": "Cannot change an order from shipped to pending."}}
```
