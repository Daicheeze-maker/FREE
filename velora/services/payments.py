"""Payment providers. Only a DEMO provider exists: it simulates a result and never charges money
or collects card data. A real gateway can be added by implementing PaymentProvider."""
import secrets
from dataclasses import dataclass


@dataclass
class PaymentResult:
    status: str        # succeeded | pending | failed
    reference: str
    message: str


class PaymentProvider:
    name = "base"
    methods: dict = {}

    def charge(self, amount_minor, currency, method, order_number) -> PaymentResult:
        raise NotImplementedError


class DemoPaymentProvider(PaymentProvider):
    name = "demo"
    methods = {
        "demo_approve": "Demo payment — simulate approval",
        "demo_decline": "Demo payment — simulate a decline",
        "cod": "Cash on delivery",
    }

    def charge(self, amount_minor, currency, method, order_number):
        ref = "DEMO-" + secrets.token_hex(6).upper()
        if method == "demo_approve":
            return PaymentResult("succeeded", ref, "Simulated approval. No real money was charged.")
        if method == "demo_decline":
            return PaymentResult("failed", ref, "Simulated decline. Try the approval option or cash on delivery.")
        if method == "cod":
            return PaymentResult("pending", ref, "Pay the courier on delivery.")
        return PaymentResult("failed", ref, "Unsupported payment method.")


def get_provider() -> PaymentProvider:
    return DemoPaymentProvider()
