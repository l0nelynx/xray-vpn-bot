import logging
import uuid

from aiogram.types import CallbackQuery
from fastapi import BackgroundTasks, Request
from pydantic import BaseModel

import app.database.requests as rq
from app.api.handlers import payment_process_background
from app.settings import secrets
from payments import InvoiceRequest, PaymentError, create_invoice, signatures


class APayWebhookData(BaseModel):
    order_id: str
    status: str
    sign: str


logger = logging.getLogger(__name__)


async def create_sbp_link(callback: CallbackQuery, amount, days: int):
    """Create an APay SBP payment link from a bot callback context.

    `amount` is in kopecks (as the bot constructor passes it); the shared
    provider works in major units, so convert before handing it over.
    """
    if await rq.is_user_banned(callback.from_user.id):
        await callback.answer("Ваш аккаунт заблокирован.", show_alert=True)
        return None

    transaction_id = uuid.uuid4()
    if await rq.get_full_transaction_info(f"{transaction_id}"):  # For safety
        transaction_id = uuid.uuid4()

    amount_rub = float(amount) / 100
    try:
        invoice = await create_invoice("apay", InvoiceRequest(
            transaction_id=str(transaction_id),
            amount=amount_rub,
            currency="RUB",
            days=days,
            user_tg_id=callback.from_user.id,
            username=callback.from_user.username,
        ))
    except PaymentError as e:
        logger.error("APay invoice creation failed: %s", e)
        return None

    await rq.create_transaction(
        user_tg_id=callback.from_user.id,
        user_transaction=str(transaction_id),
        username=callback.from_user.username,
        days=days,
        payment_method="SBP_APAY",
        amount=amount_rub,
    )
    return invoice.url


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
