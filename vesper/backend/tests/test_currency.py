import os
from decimal import Decimal

import httpx
import pytest

from app.services import currency
from tests.conftest import add

V2_OK = [{"date": "2026-10-23", "base": "PHP", "quote": "USD", "rate": 0.01724}]


def mock(handler):
    currency.transport = httpx.MockTransport(handler)


def test_rate_retrieved_from_frankfurter_v2(client):
    seen = []
    mock(lambda req: seen.append(req) or httpx.Response(200, json=V2_OK))
    r = client.get("/api/currency/rate", params={"to": "USD"}).json()
    assert r == {"base": "PHP", "quote": "USD", "rate": "0.01724", "date": "2026-10-23", "source": "live",
                 "stale": False}
    assert seen[0].url.path == "/v2/rates" and dict(seen[0].url.params) == {"base": "PHP", "quotes": "USD"}


def test_v1_shape_also_parsed(client):
    mock(lambda req: httpx.Response(200, json={"amount": 1.0, "base": "PHP", "date": "2026-10-23",
                                               "rates": {"USD": 0.01724}}))
    assert client.get("/api/currency/rate").json()["rate"] == "0.01724"


def test_rate_is_cached(client):
    hits = []
    mock(lambda req: hits.append(1) or httpx.Response(200, json=V2_OK))
    client.get("/api/currency/rate")
    r = client.get("/api/currency/rate").json()
    assert len(hits) == 1 and r["source"] == "cache"


def test_conversion_is_exact_decimal():
    # 6,800.00 PHP * 0.01724 = 117.232 -> 117.23
    assert currency.convert_centavos(680000, "0.01724") == Decimal("117.23")
    # half-up rounding: 0.125 -> 0.13 (float math would give 0.12)
    assert currency.convert_centavos(1, "12.5") == Decimal("0.13")
    assert currency.convert_centavos(10, "0.1") == Decimal("0.01")


def test_currency_formatting():
    assert currency.format_money(Decimal("1234.5"), "USD") == "$1,234.50"
    assert currency.format_money(Decimal("18500"), "PHP") == "₱18,500.00"


def test_invalid_currency(client):
    assert client.get("/api/currency/rate", params={"to": "EUR"}).status_code == 400
    assert client.get("/api/currency/rate", params={"to": "XXX"}).status_code == 400


def test_api_unavailable(client):
    mock(lambda req: httpx.Response(500, text="oops"))
    r = client.get("/api/currency/rate")
    assert r.status_code == 503 and "PHP" in r.json()["detail"]


def test_network_timeout(client):
    def slow(req):
        raise httpx.ReadTimeout("timed out", request=req)
    mock(slow)
    assert client.get("/api/currency/rate").status_code == 503


def test_malformed_and_missing_rate(client):
    mock(lambda req: httpx.Response(200, json=[{"date": "2026-10-23", "base": "PHP", "quote": "EUR", "rate": 1}]))
    assert client.get("/api/currency/rate").status_code == 503
    mock(lambda req: httpx.Response(200, json={"weird": True}))
    assert client.get("/api/currency/rate").status_code == 503


def test_stale_cache_served_when_api_fails(client, monkeypatch):
    mock(lambda req: httpx.Response(200, json=V2_OK))
    client.get("/api/currency/rate")
    monkeypatch.setattr(currency, "CACHE_TTL", -1)  # force expiry
    mock(lambda req: httpx.Response(503))
    r = client.get("/api/currency/rate").json()
    assert r["rate"] == "0.01724" and r["stale"] is True


def test_cart_totals_recalculated_in_usd(client, cart):
    mock(lambda req: httpx.Response(200, json=V2_OK))
    add(client, cart, "ylang-anao", 2)     # 13,600
    add(client, cart, "nordlys-fjord")     # 7,900
    r = client.get(f"/api/carts/{cart}", params={"currency": "USD"}).json()
    assert r["total_centavos"] == 2168000  # PHP stays the source of truth
    assert r["display"] == {"currency": "USD", "rate": "0.01724", "date": "2026-10-23",
                            "subtotal": "370.66", "shipping": "3.10", "total": "373.76"}


def test_cart_falls_back_to_php_when_rates_down(client, cart):
    mock(lambda req: httpx.Response(502))
    add(client, cart, "ylang-anao")
    r = client.get(f"/api/carts/{cart}", params={"currency": "USD"})
    assert r.status_code == 200 and r.json()["display"] is None and r.json()["total_centavos"] == 698000


@pytest.mark.skipif(not os.getenv("RUN_LIVE_API_TESTS"), reason="RUN_LIVE_API_TESTS not set")
def test_live_frankfurter(client):
    r = client.get("/api/currency/rate", params={"to": "USD"})
    assert r.status_code == 200, r.text
    assert Decimal(r.json()["rate"]) > 0
