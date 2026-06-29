import logging

from aiosend import CryptoPay

from ..config import get_crypto_bot_token
from .base import Invoice, InvoiceRequest, PaymentError, PaymentProvider

logger = logging.getLogger(__name__)


class CryptoPayProvider(PaymentProvider):
    """@CryptoBot (aiosend.CryptoPay) invoices.

    Note: CryptoPay confirmations come through aiosend's polling/webhook in
    the bot process (app/handlers/payments.py). The webapp side only creates
    the invoice URL — delivery is handled there once the user pays.
    """

    name = "crypto"
    payment_method = "CRYPTOPAY"
    supported_currencies = ("USDT", "TON", "BTC", "ETH", "LTC", "BNB", "TRX", "USDC")

    _client: CryptoPay | None = None

    @classmethod
    def _get_client(cls) -> CryptoPay:
        if cls._client is None:
            token = get_crypto_bot_token()
            if not token:
                raise PaymentError("CryptoPay token is not configured")
            cls._client = CryptoPay(token)
        return cls._client

    async def create_invoice(self, request: InvoiceRequest) -> Invoice:
        asset = request.currency.upper()
        if asset not in self.supported_currencies:
            raise PaymentError(f"CryptoPay does not support asset '{asset}'")

        client = self._get_client()
        try:
            invoice = await client.create_invoice(
                request.amount,
                asset,
                payload=str(request.days),
                description=request.description,
            )
        except Exception as e:  # aiosend wraps multiple exception types
            raise PaymentError(f"CryptoPay create_invoice failed: {e}") from e

        invoice_id = getattr(invoice, "invoice_id", None)
        url = getattr(invoice, "bot_invoice_url", None) or getattr(invoice, "mini_app_invoice_url", None)
        if not invoice_id or not url:
            raise PaymentError("CryptoPay returned an incomplete invoice")

        return Invoice(
            provider=self.name,
            invoice_id=str(invoice_id),
            url=url,
            amount=request.amount,
            currency=asset,
            raw={"invoice_id": invoice_id, "url": url},
        )
