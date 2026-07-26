import logging

from fastapi import BackgroundTasks, Request
from pydantic import BaseModel

from app.api.handlers import payment_process_background
from app.settings import secrets
from payments import signatures

logger = logging.getLogger(__name__)


class CrystalWebhookData(BaseModel):
    id: str
    state: str
    signature: str


async def payment_webhook_handler(request: Request, background_tasks: BackgroundTasks):
    try:
        raw_data = await request.json()
        logging.info(f"Получен платежный вебхук: {raw_data}")
        try:
            payment_data = CrystalWebhookData(**raw_data)
        except Exception as e:
            logging.warning(f"Invalid webhook payload: {e}")
            return {"status": "error", "message": "Invalid payload"}

        if payment_data.state == "payed":
            if not signatures.verify_crystal_webhook(
                payment_data.id, payment_data.signature, secrets.get("crystal_salt"),
            ):
                logging.warning("Invalid signature!")
                return {"status": "received", "message": "Payment status is not CONFIRMED"}
            logging.info(f'Оплата подтверждена, ID транзакции - {payment_data.id}')
            background_tasks.add_task(payment_process_background, payment_data.id)
            return {"status": "success"}

    except Exception as e:
        logging.error(f"Ошибка обработки платежа: {e}")
        return {"status": "error", "message": str(e)}
