import aiohttp
import json
import uuid
from typing import Optional, Dict, Any
import logging

from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from app.settings import secrets
import app.database.requests as rq

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PaymentProcessor:
    def __init__(self, merchant_id: str, api_key: str, bot_url: str, platega_url: str):
        self.merchant_id = merchant_id
        self.api_key = api_key
        self.bot_url = bot_url
        self.platega_url = platega_url
        self.session = None

    async def __aenter__(self):
        """Инициализация сессии при входе в контекст"""
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Закрытие сессии при выходе из контекста"""
        if self.session:
            await self.session.close()

    async def create_payment_link(self, method: int, transaction_id: str,
                                  amount: int, currency: str, desc: str) -> Optional[str]:
        """
        Создает ссылку для оплаты через платёжный шлюз
        
        Args:
            method: Метод оплаты
            transaction_id: Уникальный идентификатор транзакции
            amount: Сумма платежа
            currency: Валюта платежа
            desc: Описание платежа
            
        Returns:
            str: URL для перенаправления на оплату или None в случае ошибки
        """
        headers = {
            'Content-Type': 'application/json',
            # 'Authorization': '',
            'X-MerchantId': self.merchant_id,
            'X-Secret': self.api_key
        }

        body = {
            "paymentMethod": method,
            "id": transaction_id,
            "paymentDetails": {
                "amount": amount,
                "currency": currency
            },
            "description": desc,
            "return": self.bot_url,
            "failedUrl": self.bot_url,
            "payload": "CheezeVPN"
        }

        # Логируем запрос (без секретных данных в продакшене)
        logger.info(f"Creating payment link for transaction: {transaction_id}")
        logger.debug(f"Request headers: {headers}")
        logger.debug(f"Request body: {body}")

        try:
            async with self.session.post(
                    url=f"{self.platega_url}/transaction/process",
                    json=body,  # Используем json вместо data для автоматической сериализации
                    headers=headers
            ) as response:
                print(headers)
                print(body)
                if response.status == 200:
                    response_data = await response.json()
                    payment_link = response_data.get("redirect")
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
    if rq.get_full_transaction_info(f"{transaction_id}"):   # For safety
        transaction_id = uuid.uuid4()
    print(transaction_id)
    async with PaymentProcessor(secrets.get('platega_merchant_id'), secrets.get('platega_api_key'),
                                secrets.get('bot_url'), secrets.get('platega_url')) as processor:
        data = await processor.create_payment_link(
            method=2,
            transaction_id=f"{transaction_id}",
            amount=amount,
            currency="RUB",
            desc="Оплата подписки CheezeVPN"
        )
        if data:
            link = data.get("redirect")
            user_transaction = data.get("transactionId")
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
