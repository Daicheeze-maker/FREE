# Test report

Ran on 2026-10-26 in the development container (Python 3.13.17, Node 22.22.0).
Everything below is copied from real runs.

## Summary

| Suite | Passed | Failed | Skipped | Blocked |
|---|---|---|---|---|
| Backend: Pytest (`backend/tests`) | 47 | 0 | 2 | — |
| Frontend: Vitest (`frontend/src`) | 5 | 0 | 0 | — |
| End-to-end: Playwright (`frontend/e2e/smoke.mjs`, 14 steps) | 14 | 0 | 0 | — |
| Live PayMongo sandbox call | — | — | — | 1 (unverified) |
| Live Frankfurter call | — | — | — | 1 (unverified) |

**Blocked / unverified:** this container's network policy refuses outbound connections to
`api.paymongo.com` and `api.frankfurter.dev` (`CONNECT tunnel failed, response 403`), and no PayMongo test
credentials were available. Both integrations are therefore verified only against **mocked HTTP responses**
(httpx `MockTransport`) that follow the documented request/response formats. **No live sandbox payment
was made, and no live exchange rate was fetched.** Run the two opt-in live tests (see README) on a machine
with internet access and a test key to close this gap.

Forced live Frankfurter run in this container (expected failure, shown for transparency):

```
$ RUN_LIVE_API_TESTS=1 pytest -q tests/test_currency.py::test_live_frankfurter
E       assert 503 == 200
1 failed, 1 warning in 0.55s
$ curl https://api.paymongo.com/v1
curl: (56) CONNECT tunnel failed, response 403
```

In the end-to-end run, the currency switch therefore exercised the **fallback path**: the site showed
"Exchange rate unavailable — showing prices in PHP".

## Bugs found by testing and fixed

1. Test-data bug: a product id of `"x"` failed id validation before the seller check ran (test fixed, re-run passed).
2. React effects returned a value instead of a cleanup function, which crashed the layout in the browser (fixed, e2e re-run).
3. Shop search debounce used old URL params and wiped filters picked in the meantime (fixed by reading the live URL).
4. Changing a filter copied the old search term back into the box, undoing a cleared search (fixed).
5. Product cards overflowed horizontally at 390 px width (fixed; the e2e test now checks for horizontal overflow).
6. The confirmation page claimed an email receipt was sent; no email is sent in this demo, so the text was corrected.

## Backend: `pytest -v -rs`

```
tests/test_catalog_cart.py::test_seed_has_exactly_four_sellers_and_twenty_products PASSED [  2%]
tests/test_catalog_cart.py::test_fifth_seller_rejected PASSED            [  4%]
tests/test_catalog_cart.py::test_sixth_product_for_seller_rejected PASSED [  6%]
tests/test_catalog_cart.py::test_product_for_unknown_seller_rejected PASSED [  8%]
tests/test_catalog_cart.py::test_limits_enforced_at_service_level_after_deleting_one PASSED [ 10%]
tests/test_catalog_cart.py::test_admin_endpoints_require_token PASSED    [ 12%]
tests/test_catalog_cart.py::test_search_by_name_and_brand PASSED         [ 14%]
tests/test_catalog_cart.py::test_filters_combine PASSED                  [ 16%]
tests/test_catalog_cart.py::test_sorting PASSED                          [ 18%]
tests/test_catalog_cart.py::test_bad_filter_values_rejected PASSED       [ 20%]
tests/test_catalog_cart.py::test_product_detail_has_related_from_same_seller PASSED [ 22%]
tests/test_catalog_cart.py::test_add_update_remove_and_totals PASSED     [ 24%]
tests/test_catalog_cart.py::test_adding_same_product_twice_merges PASSED [ 26%]
tests/test_catalog_cart.py::test_cart_persists_across_requests PASSED    [ 28%]
tests/test_catalog_cart.py::test_stock_limits PASSED                     [ 30%]
tests/test_catalog_cart.py::test_invalid_quantities_rejected PASSED      [ 32%]
tests/test_catalog_cart.py::test_checkout_form_validation PASSED         [ 34%]
tests/test_catalog_cart.py::test_checkout_empty_cart_rejected PASSED     [ 36%]
tests/test_catalog_cart.py::test_client_cannot_override_price PASSED     [ 38%]
tests/test_catalog_cart.py::test_newsletter_signup PASSED                [ 40%]
tests/test_currency.py::test_rate_retrieved_from_frankfurter_v2 PASSED   [ 42%]
tests/test_currency.py::test_v1_shape_also_parsed PASSED                 [ 44%]
tests/test_currency.py::test_rate_is_cached PASSED                       [ 46%]
tests/test_currency.py::test_conversion_is_exact_decimal PASSED          [ 48%]
tests/test_currency.py::test_currency_formatting PASSED                  [ 51%]
tests/test_currency.py::test_invalid_currency PASSED                     [ 53%]
tests/test_currency.py::test_api_unavailable PASSED                      [ 55%]
tests/test_currency.py::test_network_timeout PASSED                      [ 57%]
tests/test_currency.py::test_malformed_and_missing_rate PASSED           [ 59%]
tests/test_currency.py::test_stale_cache_served_when_api_fails PASSED    [ 61%]
tests/test_currency.py::test_cart_totals_recalculated_in_usd PASSED      [ 63%]
tests/test_currency.py::test_cart_falls_back_to_php_when_rates_down PASSED [ 65%]
tests/test_currency.py::test_live_frankfurter SKIPPED (RUN_LIVE_API_...) [ 67%]
tests/test_payments.py::test_checkout_session_created_with_server_prices PASSED [ 69%]
tests/test_payments.py::test_missing_api_key PASSED                      [ 71%]
tests/test_payments.py::test_live_key_refused PASSED                     [ 73%]
tests/test_payments.py::test_unauthorized_response PASSED                [ 75%]
tests/test_payments.py::test_network_failure_to_paymongo PASSED          [ 77%]
tests/test_payments.py::test_redirect_alone_does_not_mark_paid PASSED    [ 79%]
tests/test_payments.py::test_verified_payment_updates_order_stock_and_cart PASSED [ 81%]
tests/test_payments.py::test_failed_payment_via_verify PASSED            [ 83%]
tests/test_payments.py::test_webhook_paid_and_duplicate_delivery PASSED  [ 85%]
tests/test_payments.py::test_webhook_payment_failed PASSED               [ 87%]
tests/test_payments.py::test_webhook_bad_signature_rejected PASSED       [ 89%]
tests/test_payments.py::test_webhook_without_secret_configured PASSED    [ 91%]
tests/test_payments.py::test_mock_mode_order_flow PASSED                 [ 93%]
tests/test_payments.py::test_mock_failure_and_mock_disabled_in_paymongo_mode PASSED [ 95%]
tests/test_payments.py::test_checkout_rechecks_stock PASSED              [ 97%]
tests/test_payments.py::test_live_sandbox_checkout_session SKIPPED (...) [100%]
SKIPPED [1] tests/test_currency.py:104: RUN_LIVE_API_TESTS not set
SKIPPED [1] tests/test_payments.py:225: PAYMONGO_LIVE_TEST_KEY not set
=================== 47 passed, 2 skipped, 1 warning in 4.80s ===================
```

What the groups cover:
- **Limits & seed:** exactly 4 sellers / 20 products / 5 each; 5th seller → 409; 6th product → 409; unknown seller → 404; admin token required.
- **Catalog:** search by name and brand, seller + family + price filters, all four sorts, bad parameters rejected, related products.
- **Cart:** add / merge / update / remove, totals, persistence by cart id, stock limits (including cumulative), invalid quantities.
- **Checkout:** form validation (email, PH phone, name, address, payment method), empty cart, client-sent prices ignored, stock re-checked.
- **PayMongo (mocked):** session created with server prices and Basic auth; missing key → 503; live key refused; 401 → 502 with no order left behind; network error; redirect alone does not mark the order paid; verified payment → paid + stock deducted once + cart cleared; expired session → failed; signed webhook paid; duplicate and repeated webhooks do not double-deduct; `payment.failed` webhook; bad or replayed signature rejected; missing webhook secret.
- **Frankfurter (mocked):** v2 rate fetched with the correct query; v1 response shape; caching; exact Decimal conversion and half-up rounding; formatting; invalid currency → 400; HTTP 500 / timeout / malformed body → 503; stale cache served; USD cart totals; PHP fallback when rates are down.

## Frontend: `npm test`

```
 ✓ src/lib/money.test.ts > converts PHP centavos with exact half-up rounding 2ms
 ✓ src/lib/money.test.ts > formats currency with symbol and grouping 14ms
 ✓ src/lib/money.test.ts > falls back to PHP when no rate is available 0ms
 ✓ src/components/interactions.test.tsx > quantity selector stops at stock and at 1 216ms
 ✓ src/components/interactions.test.tsx > checkout validation flags each bad field and accepts a good form 2ms
 Test Files  2 passed (2)
      Tests  5 passed (5)
```

## End-to-end: `npm run e2e` (real browser, real backend, mock payment mode)

```
✓ homepage renders with live data
✓ search and seller+family filters narrow results
✓ sort by price ascending puts the cheapest first
✓ quick view opens and closes with Escape
✓ product page: gallery, quantity, add to bag
✓ sold-out product cannot be added
✓ seller storefront lists its 5 products
✓ cart survives reload; quantity up/down updates totals
✓ Frankfurter unreachable -> PHP fallback notice shown
✓ checkout validation blocks an empty form
✓ checkout -> mock gateway -> paid confirmation
  Fjord stock after purchase: 18
✓ cart cleared after verified payment
✓ mobile menu works, no horizontal overflow
E2E smoke: all steps passed
```
