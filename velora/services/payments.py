"""Payment providers. Only a DEMO provider exists: every customer has unlimited demo credit, so it
never charges money or collects card data. A real gateway can be added by implementing PaymentProvider."""
import secrets
from dataclasses import dataclass

DEMO_CREDIT = "demo_credit"


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
    methods = {DEMO_CREDIT: "Unlimited demo credit"}

    def charge(self, amount_minor, currency, method, order_number):
        ref = "DEMO-" + secrets.token_hex(6).upper()
        if method == DEMO_CREDIT:
            return PaymentResult("succeeded", ref, "Paid with unlimited demo credit. No real money was charged.")
        return PaymentResult("failed", ref, "Unsupported payment method.")


def get_provider() -> PaymentProvider:
    return DemoPaymentProvider()
