import hashlib
import hmac
import json
import os
import time

import httpx
import pytest

from app.models import Order, Product
from app.services import paymongo
from tests.conftest import CUSTOMER, add

SECRET = "whsk_test_abc"


def checkout(client, cart, method="gcash"):
    return client.post("/api/checkout", json={"cart_id": cart, "customer": CUSTOMER, "payment_method": method})


def stock(SessionTest, pid):
    with SessionTest() as db:
        return db.get(Product, pid).stock


def signed(body: dict, secret=SECRET, ts=None):
    raw = json.dumps(body).encode()
    ts = str(ts or int(time.time()))
    sig = hmac.new(secret.encode(), f"{ts}.".encode() + raw, hashlib.sha256).hexdigest()
    return raw, {"Paymongo-Signature": f"t={ts},te={sig},li=", "Content-Type": "application/json"}


def event(evt_id, etype, resource):
    return {"data": {"id": evt_id, "type": "event",
                     "attributes": {"type": etype, "livemode": False, "data": resource}}}


@pytest.fixture
def paymongo_mode(monkeypatch):
    monkeypatch.setenv("PAYMENT_MODE", "paymongo")
    monkeypatch.setenv("PAYMONGO_SECRET_KEY", "sk_test_dummy")
    monkeypatch.setenv("PAYMONGO_WEBHOOK_SECRET", SECRET)
    calls = []
    state = {"session_status": "active", "payments": []}

    def handler(req: httpx.Request):
        calls.append(req)
        if req.method == "POST" and req.url.path == "/v1/checkout_sessions":
            return httpx.Response(200, json={"data": {"id": "cs_test_123", "type": "checkout_session", "attributes": {
                "checkout_url": "https://checkout.paymongo.com/cs_test_123",
                "payment_intent": {"id": "pi_test_123", "attributes": {"status": "awaiting_payment_method"}}}}})
        if req.method == "GET" and req.url.path == "/v1/checkout_sessions/cs_test_123":
            return httpx.Response(200, json={"data": {"id": "cs_test_123", "attributes": {
                "status": state["session_status"], "payments": state["payments"],
                "payment_intent": {"id": "pi_test_123", "attributes": {"status": "awaiting_payment_method"}}}}})
        return httpx.Response(404, json={"errors": [{"detail": "not found"}]})

    paymongo.transport = httpx.MockTransport(handler)
    return calls, state


# ---- PayMongo checkout session ----

def test_checkout_session_created_with_server_prices(client, cart, paymongo_mode):
    calls, _ = paymongo_mode
    add(client, cart, "nordlys-fjord", 2)
    r = checkout(client, cart)
    assert r.status_code == 201
    assert r.json()["checkout_url"] == "https://checkout.paymongo.com/cs_test_123"
    order = r.json()["order"]
    assert order["status"] == "pending" and order["total_centavos"] == 2 * 790000 + 18000

    body = json.loads(calls[0].content)["data"]["attributes"]
    assert calls[0].headers["authorization"].startswith("Basic ")
    assert body["payment_method_types"] == ["gcash"]
    assert body["reference_number"] == order["id"]
    assert sum(i["amount"] * i["quantity"] for i in body["line_items"]) == order["total_centavos"]
    assert all(i["currency"] == "PHP" for i in body["line_items"])
    assert body["success_url"].endswith(f"/order/{order['id']}?result=success")


def test_missing_api_key(client, cart, paymongo_mode, monkeypatch):
    monkeypatch.delenv("PAYMONGO_SECRET_KEY")
    add(client, cart, "nordlys-fjord")
    r = checkout(client, cart)
    assert r.status_code == 503 and "not configured" in r.json()["detail"]


def test_live_key_refused(client, cart, paymongo_mode, monkeypatch):
    monkeypatch.setenv("PAYMONGO_SECRET_KEY", "sk_live_realmoney")
    add(client, cart, "nordlys-fjord")
    assert checkout(client, cart).status_code == 503


def test_unauthorized_response(client, cart, paymongo_mode, SessionTest):
    paymongo.transport = httpx.MockTransport(
        lambda req: httpx.Response(401, json={"errors": [{"code": "api_key_invalid", "detail": "bad key"}]}))
    add(client, cart, "nordlys-fjord")
    r = checkout(client, cart)
    assert r.status_code == 502 and "credentials" in r.json()["detail"]
    with SessionTest() as db:
        assert db.query(Order).count() == 0  # nothing half-created


def test_network_failure_to_paymongo(client, cart, paymongo_mode):
    def boom(req):
        raise httpx.ConnectTimeout("timeout", request=req)
    paymongo.transport = httpx.MockTransport(boom)
    add(client, cart, "nordlys-fjord")
    r = checkout(client, cart)
    assert r.status_code == 502 and "reach PayMongo" in r.json()["detail"]


def test_redirect_alone_does_not_mark_paid(client, cart, paymongo_mode, SessionTest):
    add(client, cart, "nordlys-fjord")
    oid = checkout(client, cart).json()["order"]["id"]
    # User lands on ?result=success but PayMongo says no payment yet.
    r = client.post(f"/api/orders/{oid}/verify").json()
    assert r["status"] == "pending"
    assert stock(SessionTest, "nordlys-fjord") == 20


def test_verified_payment_updates_order_stock_and_cart(client, cart, paymongo_mode, SessionTest):
    _, state = paymongo_mode
    add(client, cart, "nordlys-fjord", 3)
    oid = checkout(client, cart).json()["order"]["id"]
    state["payments"] = [{"id": "pay_1", "attributes": {"status": "paid", "amount": 2388000}}]
    r = client.post(f"/api/orders/{oid}/verify").json()
    assert r["status"] == "paid" and r["payment_status"] == "paid" and r["paid_at"]
    assert stock(SessionTest, "nordlys-fjord") == 17
    assert client.get(f"/api/carts/{cart}").json()["items"] == []
    client.post(f"/api/orders/{oid}/verify")  # verifying again must not deduct again
    assert stock(SessionTest, "nordlys-fjord") == 17


def test_failed_payment_via_verify(client, cart, paymongo_mode, SessionTest):
    _, state = paymongo_mode
    add(client, cart, "nordlys-fjord")
    oid = checkout(client, cart).json()["order"]["id"]
    state["session_status"] = "expired"
    assert client.post(f"/api/orders/{oid}/verify").json()["status"] == "failed"
    assert stock(SessionTest, "nordlys-fjord") == 20
    assert len(client.get(f"/api/carts/{cart}").json()["items"]) == 1  # cart kept for retry


# ---- webhooks ----

def test_webhook_paid_and_duplicate_delivery(client, cart, paymongo_mode, SessionTest):
    add(client, cart, "velours-encre", 2)
    oid = checkout(client, cart).json()["order"]["id"]
    raw, headers = signed(event("evt_1", "checkout_session.payment.paid", {"id": "cs_test_123", "attributes": {}}))
    r = client.post("/api/webhooks/paymongo", content=raw, headers=headers)
    assert r.json() == {"received": True, "duplicate": False, "matched": True}
    assert client.get(f"/api/orders/{oid}").json()["status"] == "paid"
    assert stock(SessionTest, "velours-encre") == 0

    r = client.post("/api/webhooks/paymongo", content=raw, headers=headers)  # PayMongo retries
    assert r.status_code == 200 and r.json()["duplicate"] is True
    raw2, h2 = signed(event("evt_2", "checkout_session.payment.paid", {"id": "cs_test_123", "attributes": {}}))
    client.post("/api/webhooks/paymongo", content=raw2, headers=h2)  # different event, same payment
    assert stock(SessionTest, "velours-encre") == 0  # never negative, never double-deducted


def test_webhook_payment_failed(client, cart, paymongo_mode):
    add(client, cart, "nordlys-fjord")
    oid = checkout(client, cart).json()["order"]["id"]
    raw, headers = signed(event("evt_f", "payment.failed",
                                {"id": "pay_x", "attributes": {"payment_intent_id": "pi_test_123"}}))
    assert client.post("/api/webhooks/paymongo", content=raw, headers=headers).json()["matched"] is True
    assert client.get(f"/api/orders/{oid}").json()["status"] == "failed"


def test_webhook_bad_signature_rejected(client, cart, paymongo_mode):
    add(client, cart, "nordlys-fjord")
    oid = checkout(client, cart).json()["order"]["id"]
    body = event("evt_3", "checkout_session.payment.paid", {"id": "cs_test_123"})
    raw, headers = signed(body, secret="wrong")
    assert client.post("/api/webhooks/paymongo", content=raw, headers=headers).status_code == 400
    raw, headers = signed(body, ts=int(time.time()) - 3600)  # replayed
    assert client.post("/api/webhooks/paymongo", content=raw, headers=headers).status_code == 400
    assert client.get(f"/api/orders/{oid}").json()["status"] == "pending"


def test_webhook_without_secret_configured(client, paymongo_mode, monkeypatch):
    monkeypatch.delenv("PAYMONGO_WEBHOOK_SECRET")
    raw, headers = signed(event("e", "x", {}))
    assert client.post("/api/webhooks/paymongo", content=raw, headers=headers).status_code == 503


# ---- mock mode (local demo without credentials) ----

def test_mock_mode_order_flow(client, cart, SessionTest):
    add(client, cart, "ylang-anao", 2)
    add(client, cart, "nordlys-midnatt")
    r = checkout(client, cart, "card").json()
    oid = r["order"]["id"]
    assert r["checkout_url"].endswith(f"/pay/mock/{oid}")
    assert r["order"]["total_centavos"] == 2 * 680000 + 1080000 + 18000
    assert client.post(f"/api/payments/mock/{oid}", json={"outcome": "paid"}).json()["status"] == "paid"
    assert stock(SessionTest, "ylang-anao") == 16 and stock(SessionTest, "nordlys-midnatt") == 2
    client.post(f"/api/payments/mock/{oid}", json={"outcome": "paid"})
    assert stock(SessionTest, "ylang-anao") == 16
    # a paid order cannot be flipped to failed
    assert client.post(f"/api/payments/mock/{oid}", json={"outcome": "failed"}).json()["status"] == "paid"


def test_mock_failure_and_mock_disabled_in_paymongo_mode(client, cart, monkeypatch):
    add(client, cart, "ylang-anao")
    oid = checkout(client, cart).json()["order"]["id"]
    assert client.post(f"/api/payments/mock/{oid}", json={"outcome": "failed"}).json()["status"] == "failed"
    monkeypatch.setenv("PAYMENT_MODE", "paymongo")
    assert client.post(f"/api/payments/mock/{oid}", json={"outcome": "paid"}).status_code == 403


def test_checkout_rechecks_stock(client, cart, SessionTest):
    add(client, cart, "velours-encre", 2)
    with SessionTest() as db:
        db.get(Product, "velours-encre").stock = 1
        db.commit()
    assert checkout(client, cart).status_code == 409


# ---- live sandbox (only with real test credentials + network) ----

@pytest.mark.skipif(not os.getenv("PAYMONGO_LIVE_TEST_KEY"), reason="PAYMONGO_LIVE_TEST_KEY not set")
def test_live_sandbox_checkout_session(client, cart, monkeypatch):
    monkeypatch.setenv("PAYMENT_MODE", "paymongo")
    monkeypatch.setenv("PAYMONGO_SECRET_KEY", os.environ["PAYMONGO_LIVE_TEST_KEY"])
    add(client, cart, "nordlys-fjord")
    r = checkout(client, cart, "card")
    assert r.status_code == 201, r.text
    assert r.json()["checkout_url"].startswith("https://checkout.paymongo.com/")
