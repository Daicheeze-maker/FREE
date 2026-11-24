#!/usr/bin/env bash
# Live demo of the Aurelune REST API, one step at a time. Press Enter to move to the next step.
#
#     bash scripts/api-demo.sh                    # asks for a buyer's email and password
#     BASE=http://127.0.0.1:8080 bash scripts/api-demo.sh
#
# It shows all four HTTP methods (GET, POST, PATCH, DELETE), the status codes 200, 201, 204, 401, 409, 422 and the two
# outside APIs. Needs only curl and python3 (both are in Ubuntu). The buyer account must already exist (Create account
# on the site). Step 15 (staff CRUD) is optional: press Enter at the admin email question to skip it.
set -uo pipefail
BASE="${BASE:-http://127.0.0.1:5000}"
API="$BASE/api/v1"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
bold() { printf '\n\033[1m%s\033[0m\n' "$*"; }
step() { bold "STEP $1: $2"; shift 2; printf '\033[2m$ %s\033[0m\n' "$*"; }
pause() { printf '\n\033[2m(press Enter for the next step)\033[0m'; read -r _; }
pretty() { python3 -m json.tool 2>/dev/null || cat; }
jget() { python3 -c "import sys,json; d=json.load(sys.stdin); print(eval(sys.argv[1], {'d': d}))" "$1" 2>/dev/null; }
js() { python3 -c "import json,sys; print(json.dumps(dict(zip(sys.argv[1::2], [int(v) if v.isdigit() else v for v in sys.argv[2::2]]))))" "$@"; }
# call METHOD PATH [json body] [token]: prints "HTTP code" first, then the JSON, saves the JSON to $TMP/out.json
call() {
  local method="$1" path="$2" body="${3:-}" token="${4:-}"; local args=(-s -o "$TMP/out.json" -w "%{http_code}" -X "$method" "$API$path")
  [ -n "$token" ] && args+=(-H "Authorization: Bearer $token")
  [ -n "$body" ] && args+=(-H "Content-Type: application/json" -d "$body")
  [ -n "${IDEM:-}" ] && args+=(-H "Idempotency-Key: $IDEM")
  CODE=$(curl "${args[@]}")
}
show_error() { python3 -c "
import json
d = json.load(open('$TMP/out.json'))
e = d.get('error')
print('  ', e['status'], e['code'], '-', e['message'], ('  fields: ' + str(e['fields'])) if e.get('fields') else '') if e else print('  ', json.dumps(d)[:200])
"; }
sign_in() { # sign_in EMAIL PASSWORD -> sets TOKEN, ROLE
  call POST /auth/token "$(js email "$1" password "$2")"
  TOKEN=$(jget "d.get('token','')" < "$TMP/out.json"); ROLE=$(jget "d['user']['role']" < "$TMP/out.json")
}

if ! curl -s -m 5 -o /dev/null "$API/health"; then
  echo "The store isn't answering at $BASE. Start it first: sudo systemctl restart aurelune"; exit 1
fi

read -r -p "Buyer email: " EMAIL
read -r -s -p "Buyer password: " PASSWORD; echo
read -r -p "Admin email for the staff step 15 (press Enter to skip): " ADMIN_EMAIL
ADMIN_PASSWORD=""; [ -n "$ADMIN_EMAIL" ] && { read -r -s -p "Admin password: " ADMIN_PASSWORD; echo; }

step 1 "Health check (public, GET)" "curl $API/health"
curl -s "$API/health" | pretty
pause

step 2 "Search the catalog (public, GET with filters)" "curl '$API/products?category=dive-watches&sort=price_asc&per_page=3'"
curl -s "$API/products?category=dive-watches&sort=price_asc&per_page=3" | python3 -c "
import sys, json
d = json.load(sys.stdin)
print(f\"{d['total']} dive watches, showing {len(d['items'])}, page {d['page']} of {d['pages']}\")
for p in d['items']:
    print(f\"  #{p['id']:<3} {p['name']:<28} {p['price']['formatted']:>12}   stock {p['stock']}\")
"
pause

step 3 "No token, so the bag is refused (401 Unauthorized)" "curl -i $API/cart"
curl -s -i "$API/cart" | sed -n '1p;/^WWW-Authenticate/Ip;/^{/,$p' | tr -d '\r'
pause

step 4 "Sign in: POST the email and password, get a Bearer token" "curl -X POST $API/auth/token -d '{\"email\": ..., \"password\": ...}'"
call POST /auth/token "$(js email "$EMAIL" password "$PASSWORD")"
TOKEN=$(jget "d.get('token','')" < "$TMP/out.json")
if [ -z "$TOKEN" ]; then echo "HTTP $CODE"; show_error; echo; echo "Sign-in failed (that is the 401 error format). Check the email and password and run again."; exit 1; fi
python3 -c "
import json
d = json.load(open('$TMP/out.json'))
print('HTTP $CODE   token_type:', d['token_type'], '  expires_in:', d['expires_in'], 'seconds')
print('token :', d['token'][:28] + '...')
print('user  :', d['user']['email'], '(' + d['user']['role'] + ')   demo credit', d['user']['demo_credit']['formatted'])
"
# start from an empty bag so the demo is repeatable
call DELETE /cart "" "$TOKEN"
pause

step 5 "Look up one watch by its slug (GET)" "curl $API/products/riviera-blue-chrono-41"
call GET /products/riviera-blue-chrono-41
python3 -c "
import json
p = json.load(open('$TMP/out.json'))
print('HTTP $CODE ', p['name'], '|', p['price']['formatted'], '| sizes', p['sizes'], '| colours', p['colors'], '| engraving fee', p['engraving']['fee']['formatted'])
"
PID=$(jget "d['id']" < "$TMP/out.json"); SIZE=$(jget "d['sizes'][0]" < "$TMP/out.json"); COLOR=$(jget "d['colors'][0]" < "$TMP/out.json")
pause

step 6 "A wrong choice is refused with a clear message (422 Unprocessable)" "curl -X POST $API/cart/items -d '{\"size\": \"99 mm\", ...}'"
call POST /cart/items "$(js product_id "$PID" size "99 mm" color "$COLOR")" "$TOKEN"
echo "HTTP $CODE"; show_error
pause

step 7 "CREATE: add it to the bag (POST, 201 Created) with size, colour and engraving" "curl -X POST $API/cart/items -H 'Authorization: Bearer ...' -d '{...}'"
call POST /cart/items "$(js product_id "$PID" quantity 1 size "$SIZE" color "$COLOR" engraving MJ)" "$TOKEN"
python3 -c "
import json
c = json.load(open('$TMP/out.json'))
print('HTTP $CODE')
for i in c['items']:
    print(f\"  line #{i['id']}: {i['quantity']} x {i['product']['name']} ({i['size']}, {i['color']}, engraved '{i['engraving']}')  {i['line_total']['formatted']}\")
"
LINE=$(jget "d['items'][0]['id']" < "$TMP/out.json")
pause

step 8 "UPDATE: change the quantity of that line (PATCH, 200 OK)" "curl -X PATCH $API/cart/items/$LINE -d '{\"quantity\": 2}'"
call PATCH "/cart/items/$LINE" '{"quantity": 2}' "$TOKEN"
python3 -c "
import json
c = json.load(open('$TMP/out.json'))
print('HTTP $CODE   bag now has', c['count'], 'items, subtotal', c['subtotal']['formatted'])
"
pause

step 9 "DELETE: remove the line (204 No Content), then try to order with an empty bag (409 Conflict)" "curl -X DELETE $API/cart/items/$LINE"
call DELETE "/cart/items/$LINE" "" "$TOKEN"; echo "HTTP $CODE (nothing returned, the line is gone)"
call POST /orders '{"address_id": null}' "$TOKEN"
ADDR='{"address": {"full_name": "Juan Dela Cruz", "phone": "09171234567", "phone_country": "PH", "line1": "12 Rizal St", "city": "Naga City", "region": "Camarines Sur", "postal_code": "4400"}}'
call POST /orders "$ADDR" "$TOKEN"; echo "Ordering with an empty bag -> HTTP $CODE"; show_error
pause

step 10 "Add it again and place the order (POST, 201 Created). Money moves from the demo credit" "curl -X POST $API/orders -H 'Idempotency-Key: ...' -d '{address...}'"
call POST /cart/items "$(js product_id "$PID" quantity 1 size "$SIZE" color "$COLOR" engraving MJ)" "$TOKEN"
IDEM="demo-$(date +%s)"
call POST /orders "$ADDR" "$TOKEN"
python3 -c "
import json
d = json.load(open('$TMP/out.json'))
if 'error' in d:
    e = d['error']; print('Order refused:', e['status'], e['code'], '-', e['message']); raise SystemExit
print('HTTP $CODE')
print('order      :', d['number'], '| status', d['status'], '| total', d['total']['formatted'])
print('deliver to :', d['ship_to']['name'], d['ship_to']['phone'], '|', d['ship_to']['address'])
print('payment    :', d['payment']['status'], d['payment']['reference'])
"
ORDER_NO=$(jget "d.get('number')" < "$TMP/out.json")
pause

step 11 "Send the same request again: the same order comes back, nothing is bought twice" "curl -X POST $API/orders -H 'Idempotency-Key: $IDEM' ..."
call POST /orders "$ADDR" "$TOKEN"
echo "HTTP $CODE, order $(jget "d.get('number')" < "$TMP/out.json") (same number as step 10)"
unset IDEM
pause

step 12 "READ: order history (GET)" "curl $API/orders"
call GET "/orders?per_page=3" "" "$TOKEN"
python3 -c "
import json
d = json.load(open('$TMP/out.json'))
print(f\"HTTP $CODE   {d['total']} order(s). Newest first:\")
for o in d['items']:
    print(f\"  {o['number']}  {o['status']:<10} {o['item_count']} item(s)  {o['total']['formatted']}\")
"
pause

step 13 "Outside API 1: exchange rates from Frankfurter, through our API (GET)" "curl $API/rates"
call GET /rates
python3 -c "
import json
d = json.load(open('$TMP/out.json'))
if 'error' in d:
    e = d['error']; print('HTTP $CODE', e['code'], '-', e['message']); print('   (the clear error you get when the outside service is unreachable)')
else:
    print('HTTP $CODE   base', d['base'], '|', d['source'])
    for k, v in d['rates'].items(): print(f\"  1 PHP = {v['rate']} {k}  (date {v['date']}{', saved copy' if v['stale'] else ''})\")
"
pause

step 14 "Outside API 2: map pin to street address, Mapbox or OpenStreetMap (GET). Naga City" "curl '$API/geocode/reverse?lat=13.6218&lng=123.1948'"
call GET "/geocode/reverse?lat=13.6218&lng=123.1948" "" "$TOKEN"
python3 -c "
import json
d = json.load(open('$TMP/out.json'))
if 'error' in d:
    e = d['error']; print('HTTP $CODE', e['code'], '-', e['message']); print('   (502 = service down, 504 = timeout: the API answers instead of crashing)')
else:
    r = d['result']; print('HTTP $CODE   source:', d['source']); print('  ', {k: r.get(k) for k in ('line1', 'city', 'region', 'postal_code', 'country')})
"
pause

step 15 "Staff only: full CRUD on products (POST, PATCH, DELETE) with an admin token" "curl -X POST/PATCH/DELETE $API/products ..."
if [ -z "$ADMIN_EMAIL" ]; then
  echo "(skipped: no admin email was given)"
else
  sign_in "$ADMIN_EMAIL" "$ADMIN_PASSWORD"
  if [ -z "$TOKEN" ] || [ "$ROLE" = "customer" ]; then echo "That account is not a seller or admin, so skipped."; else
    call POST /products '{"name": "API Demo Watch", "brand": "Aurelune", "category": "field-pilot", "price": 9900, "stock": 5, "short_description": "Made through the API", "description": "A test watch created with POST.", "sizes": "38 mm,40 mm", "colors": "Black"}' "$TOKEN"
    echo "POST   -> HTTP $CODE (created)"; NEWID=$(jget "d.get('id','')" < "$TMP/out.json"); [ "$CODE" = "201" ] || show_error
    if [ -n "$NEWID" ]; then
      call PATCH "/products/$NEWID" '{"price": 8900, "stock": 2}' "$TOKEN"; echo "PATCH  -> HTTP $CODE, price now $(jget "d['price']['formatted']" < "$TMP/out.json"), stock $(jget "d['stock']" < "$TMP/out.json")"
      call GET "/products/$NEWID" "" "$TOKEN"; echo "GET    -> HTTP $CODE, $(jget "d['name']" < "$TMP/out.json")"
      call DELETE "/products/$NEWID" "" "$TOKEN"; echo "DELETE -> HTTP $CODE (archived, kept for order history)"
      call GET "/products/$NEWID"; echo "GET as a shopper -> HTTP $CODE (no longer in the shop)"
    fi
    echo; echo "A buyer trying the same POST is refused:"
    call POST /products '{"name": "Nope"}' "$(curl -s -X POST "$API/auth/token" -H 'Content-Type: application/json' -d "$(js email "$EMAIL" password "$PASSWORD")" | jget "d.get('token','')")"
    echo "POST as a buyer -> HTTP $CODE"; show_error
  fi
fi

echo
bold "Done. The same list of endpoints is on the website at $BASE/api/docs"
