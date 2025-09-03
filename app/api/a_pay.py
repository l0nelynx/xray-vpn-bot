import requests, hashlib, aiohttp
import aiohttp
import json
import uuid
from typing import Optional, Dict, Any
import logging

from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
import app.database.requests as rq

from app.settings import bot, secrets

import app.keyboards as kb
import app.handlers.tools as tools

from fastapi import Request, BackgroundTasks
from app.api.handlers import payment_process_background

# order_id = "abc123"
# amount = 10000
# secret = "your_secret"
# sign = hashlib.md5(f"{order_id}:{amount}:{secret}".encode()).hexdigest()
#
# params = {
#     "client_id": 123,
#     "order_id": order_id,
#     "amount": amount,
#     "sign": sign
# }
#
# response = requests.get("https://apays.io/backend/create_order", params=params)
# print(response.json())

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PaymentProcessor:
    def __init__(self, client_id: int, secret: str, api_url: str):
        self.client_id = client_id
        self.secret = secret
        self.api_url = api_url
        self.session = None

    async def __aenter__(self):
        """Инициализация сессии при входе в контекст"""
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Закрытие сессии при выходе из контекста"""
        if self.session:
            await self.session.close()

    async def create_payment_link(self, order_id: str,
                                  amount: int) -> Optional[str]:
        headers = {
            'Content-Type': 'application/json'
        }

        body = {
            "client_id": self.client_id,
            "order_id": f"{order_id}",
            "amount": amount*100,
            "sign": f'{hashlib.md5(f"{order_id}:{amount*100}:{self.secret}".encode()).hexdigest()}'

        }
        # Логируем запрос (без секретных данных в продакшене)
        logger.info(f"Creating payment link for transaction: {order_id}")
        logger.debug(f"Request headers: {headers}")
        logger.debug(f"Request body: {body}")
        try:
            async with self.session.get(
                    url=f"{self.api_url}/backend/create_order",
                    params=body
                    #json=body
                    #headers=headers
            ) as response:
                print(headers)
                print(body)
                if response.status == 200:
                    response_data = await response.json()
                    payment_link = response_data.get("url")
                    print(f"Status{response_data}")
                    logger.info(f"Payment link created successfully: {payment_link}")
                    return response_data
                else:
                    error_text = await response.text()
                    logger.error(f"Error creating payment link: {response.status} - {error_text}")
                    return None

        except aiohttp.ClientError as e:
            logger.error(f"HTTP client error: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return None


async def create_sbp_link(callback: CallbackQuery, amount, days: int):
    transaction_id = uuid.uuid4()
    if await rq.get_full_transaction_info(f"{transaction_id}"):  # For safety
        transaction_id = uuid.uuid4()
    print(transaction_id)
    async with PaymentProcessor(secrets.get('apay_id'), secrets.get('apay_secret'),
                                secrets.get('apay_api_url')) as processor:
        data = await processor.create_payment_link(
            order_id=f"{transaction_id}",
            amount=amount
        )
        if data:
            link = data.get("url")
            # user_transaction = data.get("transactionId")
            status = data.get("status")
            user_transaction = f"{transaction_id}"
            await rq.create_transaction(user_tg_id=callback.from_user.id,
                                        user_transaction=user_transaction,
                                        username=callback.from_user.username,
                                        days=days)
            return link
        # Testing only
        user_transaction = f"{transaction_id}"
        await rq.create_transaction(user_tg_id=callback.from_user.id,
                                    user_transaction=user_transaction,
                                    username=callback.from_user.username,
                                    days=days)


async def payment_webhook_handler(request: Request, background_tasks: BackgroundTasks):
    try:
        payment_data = await request.json()
        # Получаем данные платежа
        logging.info(f"Получен платежный вебхук: {payment_data}")
        print('Webbhook получен')
        print(request.headers)
        if payment_data["status"] == "approved":
            print(payment_data)
            sign = hashlib.md5(f"{payment_data['order_id']}:{payment_data['status']}:{secrets.get('apay_secret')}".encode()).hexdigest()
            if payment_data['sign'] == sign:
                print('Оплата подтверждена')
                print(f'ID транзакции - {payment_data["order_id"]}')
                background_tasks.add_task(payment_process_background, payment_data['order_id'])
                return {"status": "success"}
            else:
                return {"status": "received", "message": "Payment status is not CONFIRMED"}
    except Exception as e:
        logging.error(f"Ошибка обработки платежа: {e}")
        return {"status": "error", "message": str(e)}
