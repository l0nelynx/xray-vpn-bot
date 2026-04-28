from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import ClassVar


class PaymentError(Exception):
    """Raised when a payment provider fails to create or process an invoice."""


@dataclass(frozen=True)
class InvoiceRequest:
    """Provider-agnostic invoice request.

    `transaction_id` is generated upstream and reused as the merchant order id
    so that webhooks can match the payment back to the local transaction row.
    """
    transaction_id: str
    amount: float
    currency: str
    days: int
    user_tg_id: int
    username: str | None = None
    description: str | None = None


@dataclass(frozen=True)
class Invoice:
    """Provider-agnostic response."""
    provider: str
    invoice_id: str
    url: str
    amount: float
    currency: str
    raw: dict = field(default_factory=dict)


class PaymentProvider(ABC):
    """Base class for all webapp payment providers.

    Each provider:
      1. Knows how to turn an InvoiceRequest into a hosted payment URL.
      2. Declares the currencies it supports — used by the dashboard
         constructor to gate provider/currency combinations.
      3. Maps to a `payment_method` string compatible with the existing
         shared transactions table, so existing bot-side webhooks
         (in main.py) can deliver the subscription on confirmation.
    """

    name: ClassVar[str]
    payment_method: ClassVar[str]
    supported_currencies: ClassVar[tuple[str, ...]]

    def supports(self, currency: str) -> bool:
        return currency.upper() in {c.upper() for c in self.supported_currencies}

    @abstractmethod
    async def create_invoice(self, request: InvoiceRequest) -> Invoice:
        ...


SupportedCurrencies = {
    "apay": ("RUB",),
    "crystal": ("RUB", "USD", "EUR"),
    "crypto": ("USDT", "TON", "BTC", "ETH", "LTC", "BNB", "TRX", "USDC"),
}
