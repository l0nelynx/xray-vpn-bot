import logging
import uuid

from aiogram.types import CallbackQuery
from fastapi import BackgroundTasks, Request
from pydantic import BaseModel

import app.database.requests as rq
from app.api.handlers import payment_process_background
from app.settings import secrets
from payments import InvoiceRequest, PaymentError, create_invoice, signatures

logger = logging.getLogger(__name__)


class PlategaWebhookData(BaseModel):
    id: str
    amount: float
    currency: str
    status: str
    paymentMethod: int | None = None
    payload: str | None = None


async def create_platega_link(callback: CallbackQuery, amount: float, days: int,
                              currency: str = "RUB"):
    """Create a Platega payment link from a bot callback context."""
    if await rq.is_user_banned(callback.from_user.id):
        await callback.answer("Ваш аккаунт заблокирован.", show_alert=True)
        return None

    try:
        invoice = await create_invoice("platega", InvoiceRequest(
            transaction_id=str(uuid.uuid4()),
            amount=float(amount),
            currency=currency,
            days=days,
            user_tg_id=callback.from_user.id,
            username=callback.from_user.username,
        ))
    except PaymentError as e:
        logger.error("Platega invoice creation failed: %s", e)
        return None

    # Platega's own transactionId is the key the webhook reports back.
    await rq.create_transaction(
        user_tg_id=callback.from_user.id,
        user_transaction=invoice.invoice_id,
        username=callback.from_user.username,
        days=days,
        payment_method="PLATEGA",
        amount=float(amount),
    )
    return invoice.url


async def payment_webhook_handler(request: Request, background_tasks: BackgroundTasks):
    """Handle POST /bot/platega_webhook callback from Platega.

    Platega authenticates the callback by sending the merchant's own
    X-MerchantId / X-Secret headers — we verify equality with our config.
    """
    try:
        if not signatures.verify_platega_webhook(
            request.headers.get("X-MerchantId", ""),
            request.headers.get("X-Secret", ""),
            secrets.get("platega_merchant_id", "") or "",
            secrets.get("platega_api_key", "") or "",
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
