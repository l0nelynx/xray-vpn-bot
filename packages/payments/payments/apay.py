import hashlib
import logging

import aiohttp

from .base import Invoice, InvoiceRequest, PaymentError, PaymentProvider
from .config import get_config

logger = logging.getLogger(__name__)


class APayProvider(PaymentProvider):
    """SBP via APay."""

    name = "apay"
    payment_method = "SBP_APAY"
    supported_currencies = ("RUB",)

    _session: aiohttp.ClientSession | None = None

    @classmethod
    def _get_session(cls) -> aiohttp.ClientSession:
        if cls._session is None or cls._session.closed:
            cls._session = aiohttp.ClientSession()
        return cls._session

    async def create_invoice(self, request: InvoiceRequest) -> Invoice:
        cfg = get_config()
        client_id = cfg.apay_id
        secret = cfg.apay_secret
        api_url = cfg.apay_api_url
        if not (client_id and secret and api_url):
            raise PaymentError("APay is not configured")

        # APay expects the amount in kopecks (integer).
        amount_minor = int(round(request.amount * 100))
        sign = hashlib.md5(
            f"{request.transaction_id}:{amount_minor}:{secret}".encode()
        ).hexdigest()

        params = {
            "client_id": client_id,
            "order_id": request.transaction_id,
            "amount": amount_minor,
            "sign": sign,
        }

        try:
            async with self._get_session().get(
                f"{api_url}/backend/create_order",
                params=params,
            ) as response:
                if response.status != 200:
                    body = await response.text()
                    raise PaymentError(f"APay HTTP {response.status}: {body}")
                data = await response.json()
        except aiohttp.ClientError as e:
            raise PaymentError(f"APay HTTP error: {e}") from e

        url = data.get("url")
        if not url:
            raise PaymentError(f"APay response missing 'url': {data}")

        return Invoice(
            provider=self.name,
            invoice_id=request.transaction_id,
            url=url,
            amount=request.amount,
            currency="RUB",
            raw=data,
        )
