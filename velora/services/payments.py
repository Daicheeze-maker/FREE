"""Payment providers. Only a DEMO provider exists: every buyer starts with PHP 500,000 of demo credit
(spent at checkout), so it never charges real money or collects card data. A real gateway can be added by implementing PaymentProvider."""
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
    methods = {DEMO_CREDIT: "Demo credit"}

    def charge(self, amount_minor, currency, method, order_number):
        ref = "DEMO-" + secrets.token_hex(6).upper()
        if method == DEMO_CREDIT:
            return PaymentResult("succeeded", ref, "Paid with demo credit. No real money was charged.")
        return PaymentResult("failed", ref, "Unsupported payment method.")


def get_provider() -> PaymentProvider:
    return DemoPaymentProvider()
