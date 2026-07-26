"""Telegram Stars invoice-link provider."""
from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

import aiohttp

from .base import Invoice, InvoiceRequest, PaymentError, PaymentProvider
from .config import get_config


def validate_stars_payment(
    transaction: Mapping[str, Any] | None,
    *,
    user_tg_id: int,
    currency: str,
    total_amount: int,
) -> bool:
    """Validate an incoming Telegram payment against the immutable DB snapshot."""
    if not transaction or transaction.get("status") != "created":
        return False
    try:
        amount = float(transaction.get("amount") or 0)
        return (
            transaction.get("user_tg_id") == user_tg_id
            and transaction.get("payment_method") == "TG_STARS"
            and currency == "XTR"
            and amount > 0
            and amount.is_integer()
            and int(amount) == total_amount
        )
    except (TypeError, ValueError):
        return False


class TelegramStarsProvider(PaymentProvider):
    name = "stars"
    payment_method = "TG_STARS"
    supported_currencies = ("XTR",)
    surfaces = frozenset({"bot", "miniapp"})

    _session: aiohttp.ClientSession | None = None

    @classmethod
    def _get_session(cls) -> aiohttp.ClientSession:
        if cls._session is None or cls._session.closed:
            cls._session = aiohttp.ClientSession()
        return cls._session

    async def create_invoice(self, request: InvoiceRequest) -> Invoice:
        token = get_config().bot_token
        amount = float(request.amount)
        if not token:
            raise PaymentError("Telegram bot token is not configured")
        if request.currency.upper() != "XTR" or amount <= 0 or not amount.is_integer():
            raise PaymentError("Telegram Stars amount must be a positive integer XTR value")

        payload = {
            "title": request.description or "VPN subscription",
            "description": f"Subscription for {request.days} days",
            "payload": request.transaction_id,
            "provider_token": "",
            "currency": "XTR",
            "prices": json.dumps(
                [{"label": "VPN subscription", "amount": int(amount)}]
            ),
        }
        try:
            async with self._get_session().post(
                f"https://api.telegram.org/bot{token}/createInvoiceLink",
                data=payload,
            ) as response:
                data = await response.json()
        except (aiohttp.ClientError, ValueError) as exc:
            raise PaymentError(f"Telegram Stars request failed: {exc}") from exc
        if not data.get("ok") or not data.get("result"):
            raise PaymentError(f"Telegram Stars error: {data.get('description', data)}")
        return Invoice(
            provider=self.name,
            invoice_id=request.transaction_id,
            url=str(data["result"]),
            amount=amount,
            currency="XTR",
            raw=data,
        )
