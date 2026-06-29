import json
import logging
from typing import Any

import aiohttp

from ..config import (
    get_crystal_login,
    get_crystal_secret,
    get_crystal_webhook,
)
from .base import Invoice, InvoiceRequest, PaymentError, PaymentProvider

logger = logging.getLogger(__name__)

INVOICE_LIFETIME = 3600


class CrystalPayProvider(PaymentProvider):
    """CrystalPay invoice (purchase type). Mirrors app/api/crystal_pay.py."""

    name = "crystal"
    payment_method = "CRYSTAL_PAY"
    supported_currencies = ("RUB", "USD", "EUR")

    _session: aiohttp.ClientSession | None = None

    @classmethod
    def _get_session(cls) -> aiohttp.ClientSession:
        if cls._session is None or cls._session.closed:
            cls._session = aiohttp.ClientSession()
        return cls._session

    async def _request(self, method: str, function: str, params: dict[str, Any]) -> dict:
        url = f"https://api.crystalpay.io/v2/{method}/{function}/"
        try:
            async with self._get_session().post(
                url,
                json=params,
                headers={"Content-Type": "application/json"},
            ) as response:
                payload = await response.json()
        except aiohttp.ClientError as e:
            raise PaymentError(f"CrystalPay HTTP error: {e}") from e
        except json.JSONDecodeError as e:
            raise PaymentError(f"CrystalPay JSON decode: {e}") from e

        if payload.get("error"):
            raise PaymentError(f"CrystalPay error: {payload.get('errors')}")
        return payload

    async def create_invoice(self, request: InvoiceRequest) -> Invoice:
        login = get_crystal_login()
        secret = get_crystal_secret()
        if not (login and secret):
            raise PaymentError("CrystalPay is not configured")

        params = {
            "auth_login": login,
            "auth_secret": secret,
            "amount": request.amount,
            "type": "purchase",
            "lifetime": INVOICE_LIFETIME,
            "description": request.description or f"Subscription {request.days}d",
            "amount_currency": request.currency.upper(),
        }
        webhook = get_crystal_webhook()
        if webhook:
            params["callback_url"] = webhook

        data = await self._request("invoice", "create", params)

        invoice_id = data.get("id")
        url = data.get("url")
        if not invoice_id or not url:
            raise PaymentError(f"CrystalPay response incomplete: {data}")

        return Invoice(
            provider=self.name,
            invoice_id=str(invoice_id),
            url=url,
            amount=request.amount,
            currency=request.currency.upper(),
            raw=data,
        )
