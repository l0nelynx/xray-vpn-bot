import logging

from fastapi import BackgroundTasks, Request
from pydantic import BaseModel

from app.api.handlers import payment_process_background
from app.settings import secrets
from payments import signatures

logger = logging.getLogger(__name__)


class PlategaWebhookData(BaseModel):
    id: str
    amount: float
    currency: str
    status: str
    paymentMethod: int | None = None
    payload: str | None = None


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
