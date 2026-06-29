import logging

import aiohttp

from ..config import (
    get_platega_api_key,
    get_platega_merchant_id,
    get_platega_payment_method,
    get_platega_url,
)
from .base import Invoice, InvoiceRequest, PaymentError, PaymentProvider

logger = logging.getLogger(__name__)


def _resolve_method(requested: str | None) -> int:
    """Use per-button method when set & numeric, else fall back to config default."""
    if requested and requested.lower() != "default":
        try:
            return int(requested)
        except (TypeError, ValueError):
            logger.warning("Platega: ignoring non-numeric method %r", requested)
    return get_platega_payment_method()


class PlategaProvider(PaymentProvider):
    """Platega.io payment gateway. Mirrors app/api/platega.py PaymentProcessor."""

    name = "platega"
    payment_method = "PLATEGA"
    supported_currencies = ("RUB",)

    _session: aiohttp.ClientSession | None = None

    @classmethod
    def _get_session(cls) -> aiohttp.ClientSession:
        if cls._session is None or cls._session.closed:
            cls._session = aiohttp.ClientSession()
        return cls._session

    async def create_invoice(self, request: InvoiceRequest) -> Invoice:
        merchant_id = get_platega_merchant_id()
        api_key = get_platega_api_key()
        api_url = get_platega_url()
        method = _resolve_method(request.method)

        if not (merchant_id and api_key and api_url):
            raise PaymentError("Platega is not configured")

        body = {
            "paymentMethod": method,
            "paymentDetails": {
                "amount": float(request.amount),
                "currency": request.currency.upper(),
            },
            "description": request.description or f"TgId:{request.user_tg_id}",
            "payload": request.transaction_id,
        }

        headers = {
            "X-MerchantId": merchant_id,
            "X-Secret": api_key,
            "Content-Type": "application/json",
        }

        try:
            async with self._get_session().post(
                f"{api_url}/v2/transaction/process",
                json=body,
                headers=headers,
            ) as response:
                if response.status != 200:
                    text = await response.text()
                    raise PaymentError(f"Platega HTTP {response.status}: {text}")
                data = await response.json()
        except aiohttp.ClientError as e:
            raise PaymentError(f"Platega HTTP error: {e}") from e

        transaction_id = data.get("transactionId")
        url = data.get("redirect") or data.get("url")
        if not transaction_id or not url:
            raise PaymentError(f"Platega response incomplete: {data}")

        return Invoice(
            provider=self.name,
            invoice_id=str(transaction_id),
            url=url,
            amount=float(request.amount),
            currency=request.currency.upper(),
            raw=data,
        )
