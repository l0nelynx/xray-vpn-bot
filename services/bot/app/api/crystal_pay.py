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


class CrystalWebhookData(BaseModel):
    id: str
    state: str
    signature: str


async def crystal_create_link(callback: CallbackQuery, amount, currency: str, days: int):
    if await rq.is_user_banned(callback.from_user.id):
        await callback.answer("Ваш аккаунт заблокирован.", show_alert=True)
        return None

    try:
        invoice = await create_invoice("crystal", InvoiceRequest(
            transaction_id=str(uuid.uuid4()),
            amount=float(amount),
            currency=currency,
            days=days,
            user_tg_id=callback.from_user.id,
            username=callback.from_user.username,
        ))
    except PaymentError as e:
        logging.error("CrystalPay invoice creation error: %s", e)
        return "CrystalPay api error"

    await rq.create_transaction(
        user_tg_id=callback.from_user.id,
        user_transaction=invoice.invoice_id,
        username=callback.from_user.username,
        days=days,
        payment_method="CRYSTAL_PAY",
        amount=float(amount),
    )
    return invoice.url


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
