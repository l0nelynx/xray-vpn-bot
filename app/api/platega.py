import hmac
import logging
import uuid
from typing import Optional

import aiohttp
from aiogram.types import CallbackQuery
from fastapi import BackgroundTasks, Request
from pydantic import BaseModel

import app.database.requests as rq
from app.api.handlers import payment_process_background
from app.settings import secrets

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PlategaWebhookData(BaseModel):
    id: str
    amount: float
    currency: str
    status: str
    paymentMethod: int | None = None
    payload: str | None = None


class PaymentProcessor:
    """Platega.io payment client.

    Auth via X-MerchantId / X-Secret headers (see https://docs.platega.io).
    """

    def __init__(self, merchant_id: str, api_key: str, api_url: str,
                 default_method: int = 2):
        self.merchant_id = merchant_id
        self.api_key = api_key
        self.api_url = api_url.rstrip("/")
        self.default_method = default_method
        self.session: aiohttp.ClientSession | None = None

    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    def _headers(self) -> dict:
        return {
            "X-MerchantId": self.merchant_id,
            "X-Secret": self.api_key,
            "Content-Type": "application/json",
        }

    async def create_payment(
        self,
        amount: float,
        currency: str = "RUB",
        description: str = "",
        payload: Optional[str] = None,
        return_url: Optional[str] = None,
        failed_url: Optional[str] = None,
        payment_method: Optional[int] = None,
    ) -> Optional[dict]:
        body: dict = {
            "paymentMethod": payment_method or self.default_method,
            "paymentDetails": {"amount": amount, "currency": currency},
        }
        if description:
            body["description"] = description
        if payload:
            body["payload"] = payload
        if return_url:
            body["return"] = return_url
        if failed_url:
            body["failedUrl"] = failed_url

        logger.info(f"Platega create payment: amount={amount} {currency}")
        try:
            async with self.session.post(
                url=f"{self.api_url}/v2/transaction/process",
                json=body,
                headers=self._headers(),
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    logger.info(f"Platega payment created: {data.get('transactionId')}")
                    return data
                error_text = await response.text()
                logger.error(f"Platega create error {response.status}: {error_text}")
                return None
        except aiohttp.ClientError as e:
            logger.error(f"Platega HTTP error: {e}")
            return None
        except Exception as e:
            logger.error(f"Platega unexpected error: {e}")
            return None

    async def get_status(self, transaction_id: str) -> Optional[dict]:
        try:
            async with self.session.get(
                url=f"{self.api_url}/transaction/{transaction_id}",
                headers=self._headers(),
            ) as response:
                if response.status == 200:
                    return await response.json()
                logger.error(f"Platega status error {response.status}")
                return None
        except Exception as e:
            logger.error(f"Platega status fetch error: {e}")
            return None


async def create_platega_link(callback: CallbackQuery, amount: float, days: int,
                              currency: str = "RUB"):
    """Create a Platega payment link from a bot callback context."""
    if await rq.is_user_banned(callback.from_user.id):
        await callback.answer("Ваш аккаунт заблокирован.", show_alert=True)
        return None

    local_payload = f"TgId:{callback.from_user.id};uid:{uuid.uuid4()}"

    async with PaymentProcessor(
        merchant_id=secrets.get("platega_merchant_id"),
        api_key=secrets.get("platega_api_key"),
        api_url=secrets.get("platega_url", "https://app.platega.io"),
        default_method=int(secrets.get("platega_payment_method", 2)),
    ) as processor:
        data = await processor.create_payment(
            amount=float(amount),
            currency=currency,
            description=f"TgId:{callback.from_user.id}",
            payload=local_payload,
        )
        if not data:
            return None

        transaction_id = data.get("transactionId")
        url = data.get("redirect") or data.get("url")
        if not transaction_id or not url:
            logger.error(f"Platega response missing fields: {data}")
            return None

        await rq.create_transaction(
            user_tg_id=callback.from_user.id,
            user_transaction=str(transaction_id),
            username=callback.from_user.username,
            days=days,
            payment_method="PLATEGA",
            amount=float(amount),
        )
        return url


async def payment_webhook_handler(request: Request, background_tasks: BackgroundTasks):
    """Handle POST /bot/platega_webhook callback from Platega.

    Platega authenticates the callback by sending the merchant's own
    X-MerchantId / X-Secret headers — we verify equality with our config.
    """
    try:
        merchant_id_header = request.headers.get("X-MerchantId", "")
        secret_header = request.headers.get("X-Secret", "")
        expected_merchant_id = secrets.get("platega_merchant_id", "") or ""
        expected_secret = secrets.get("platega_api_key", "") or ""

        if not (
            hmac.compare_digest(merchant_id_header, expected_merchant_id)
            and hmac.compare_digest(secret_header, expected_secret)
        ):
            logger.warning("Platega webhook: invalid auth headers")
            return {"status": "error", "message": "unauthorized"}

        raw_data = await request.json()
        logger.info(f"Platega webhook received: {raw_data}")

        try:
            payment_data = PlategaWebhookData(**raw_data)
        except Exception as e:
            logger.warning(f"Platega webhook: invalid payload: {e}")
            return {"status": "error", "message": "invalid payload"}

        if payment_data.status == "CONFIRMED":
            logger.info(f"Platega payment confirmed: {payment_data.id}")
            background_tasks.add_task(payment_process_background, payment_data.id)
            return {"status": "success"}

        # CANCELED / CHARGEBACKED — just acknowledge so Platega stops retrying
        logger.info(f"Platega payment status {payment_data.status} for {payment_data.id}")
        return {"status": "received"}

    except Exception as e:
        logger.error(f"Platega webhook error: {e}")
        return {"status": "error", "message": str(e)}
