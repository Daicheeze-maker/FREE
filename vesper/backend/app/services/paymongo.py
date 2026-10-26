"""PayMongo Hosted Checkout (test mode). Docs: https://developers.paymongo.com/docs/checkout-api"""
import hashlib
import hmac
import time

import httpx

from ..config import env

API = "https://api.paymongo.com/v1"
transport: httpx.BaseTransport | None = None  # tests inject httpx.MockTransport here
SIGNATURE_TOLERANCE = 300  # seconds; rejects replayed webhooks


class PayMongoError(Exception):
    def __init__(self, message: str, status: int = 502):
        super().__init__(message)
        self.status = status


def _client() -> httpx.Client:
    key = env("PAYMONGO_SECRET_KEY")
    if not key:
        raise PayMongoError("PayMongo is not configured (PAYMONGO_SECRET_KEY missing).", 503)
    if not key.startswith("sk_test_"):
        # This prototype must never touch live money.
        raise PayMongoError("Only PayMongo test keys (sk_test_...) are allowed in this prototype.", 503)
    return httpx.Client(base_url=API, auth=(key, ""), transport=transport, timeout=15)


def _call(method: str, path: str, **kwargs) -> dict:
    with _client() as client:
        try:
            res = client.request(method, path, **kwargs)
        except httpx.HTTPError as exc:
            raise PayMongoError(f"Could not reach PayMongo: {exc.__class__.__name__}") from exc
    if res.status_code in (401, 403):
        raise PayMongoError("PayMongo rejected the API credentials.", 502)
    if res.status_code >= 400:
        try:
            detail = res.json()["errors"][0]["detail"]
        except Exception:
            detail = res.text[:200]
        raise PayMongoError(f"PayMongo error {res.status_code}: {detail}", 502)
    return res.json()["data"]


def create_checkout_session(order, payment_methods: list[str], success_url: str, cancel_url: str) -> dict:
    """Amounts come from the server-side order, never from the client."""
    body = {
        "data": {
            "attributes": {
                "billing": {"name": order.customer.name, "email": order.customer.email, "phone": order.customer.phone},
                "line_items": [
                    {"currency": "PHP", "amount": i.unit_price_centavos, "name": f"{i.name} - {i.seller_name}",
                     "quantity": i.quantity}
                    for i in order.items
                ] + [{"currency": "PHP", "amount": order.shipping_centavos, "name": "Shipping (demo rate)",
                      "quantity": 1}],
                "payment_method_types": payment_methods,
                "reference_number": order.id,
                "description": f"Vesper demo order {order.id}",
                "send_email_receipt": False,
                "show_line_items": True,
                "success_url": success_url,
                "cancel_url": cancel_url,
                "metadata": {"order_id": order.id},
            }
        }
    }
    data = _call("POST", "/checkout_sessions", json=body)
    pi = data["attributes"].get("payment_intent") or {}
    return {"id": data["id"], "checkout_url": data["attributes"]["checkout_url"], "payment_intent_id": pi.get("id")}


def session_payment_status(session_id: str) -> str:
    """Ask PayMongo directly: 'paid', 'failed' or 'pending'. Used instead of trusting the redirect."""
    attrs = _call("GET", f"/checkout_sessions/{session_id}")["attributes"]
    payments = attrs.get("payments") or []
    if any(p.get("attributes", {}).get("status") == "paid" for p in payments):
        return "paid"
    pi_status = ((attrs.get("payment_intent") or {}).get("attributes") or {}).get("status")
    if pi_status == "succeeded":
        return "paid"
    if attrs.get("status") == "expired" or any(p.get("attributes", {}).get("status") == "failed" for p in payments):
        return "failed"
    return "pending"


def verify_signature(raw_body: bytes, header: str, secret: str, now: float | None = None) -> bool:
    """Paymongo-Signature: t=<ts>,te=<test sig>,li=<live sig>; sig = HMAC-SHA256(secret, f"{t}.{body}")."""
    parts = dict(p.split("=", 1) for p in header.split(",") if "=" in p)
    ts, sig = parts.get("t"), parts.get("te")  # test mode only
    if not ts or not sig or not ts.isdigit():
        return False
    if abs((now or time.time()) - int(ts)) > SIGNATURE_TOLERANCE:
        return False
    expected = hmac.new(secret.encode(), f"{ts}.".encode() + raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, sig)
