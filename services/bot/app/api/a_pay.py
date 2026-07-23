import logging

from fastapi import BackgroundTasks, Request
from pydantic import BaseModel

from app.api.handlers import payment_process_background
from app.settings import secrets
from payments import signatures


class APayWebhookData(BaseModel):
    order_id: str
    status: str
    sign: str


logger = logging.getLogger(__name__)


async def payment_webhook_handler(request: Request, background_tasks: BackgroundTasks):
    try:
        raw_data = await request.json()
        logging.info(f"Получен платежный вебхук: {raw_data}")
        try:
            payment_data = APayWebhookData(**raw_data)
        except Exception as e:
            logging.warning(f"Invalid webhook payload: {e}")
            return {"status": "error", "message": "Invalid payload"}

        if payment_data.status == "approved":
            if signatures.verify_apay_webhook(
                payment_data.order_id, payment_data.status,
                payment_data.sign, secrets.get("apay_secret"),
            ):
                logging.info(f'Оплата подтверждена, ID транзакции - {payment_data.order_id}')
                background_tasks.add_task(payment_process_background, payment_data.order_id)
                return {"status": "success"}
            else:
                return {"status": "received", "message": "Payment status is not CONFIRMED"}
    except Exception as e:
        logging.error(f"Ошибка обработки платежа: {e}")
        return {"status": "error", "message": str(e)}
