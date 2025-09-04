import aiohttp
import json
import hashlib
import hmac
import asyncio
import logging
from typing import Dict, Any, Optional
from fastapi import Request, BackgroundTasks
from app.api.handlers import payment_process_background
from app.settings import bot, secrets
import app.database.requests as rq
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class InvoiceType:
    topup = "topup"
    purchase = "purchase"


class PayoffSubtractFrom:
    balance = "balance"
    amount = "amount"


class CrystalUtils:
    """Дополнительный класс, содержащий в себе дополнительные функции для работы SDK"""

    @staticmethod
    def concatParams(concatList: Dict, kwargs: Dict) -> Dict:
        """Соединяет необязательные параметры с обязательными"""
        temp = concatList.copy()
        temp.update(kwargs)
        return temp

    @staticmethod
    async def requestsApi(method: str, function: str, params: Dict) -> Dict:
        """Асинхронная отправка запроса на API"""
        url = f"https://api.crystalpay.io/v2/{method}/{function}/"

        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(
                        url,
                        json=params,
                        headers={'Content-Type': 'application/json'}
                ) as response:
                    response_data = await response.json()
                    print('POST')
                    print(params)
                    if response_data.get("error"):
                        raise Exception(response_data.get('errors', 'Unknown error'))

                    # Убираем из JSON ответа сообщения об ошибках
                    response_data.pop("error", None)
                    response_data.pop("errors", None)

                    return response_data

            except aiohttp.ClientError as e:
                raise Exception(f"HTTP error: {e}")
            except json.JSONDecodeError as e:
                raise Exception(f"JSON decode error: {e}")


class CrystalPAY:
    """Главный класс для работы с CrystalApi"""

    def __init__(self, auth_login: str, auth_secret: str, salt: str):
        self.auth_login = auth_login
        self.auth_secret = auth_secret
        self.salt = salt
        self.utils = CrystalUtils()

        # Создание подклассов
        self.Me = self.Me(auth_login, auth_secret, self.utils)
        self.Method = self.Method(auth_login, auth_secret, self.utils)
        self.Balance = self.Balance(auth_login, auth_secret, self.utils)
        self.Invoice = self.Invoice(auth_login, auth_secret, self.utils)
        self.Payoff = self.Payoff(auth_login, auth_secret, salt, self.utils)
        self.Ticker = self.Ticker(auth_login, auth_secret, self.utils)

    class Me:
        def __init__(self, auth_login: str, auth_secret: str, utils: CrystalUtils):
            self.auth_login = auth_login
            self.auth_secret = auth_secret
            self.utils = utils

        async def getinfo(self) -> Dict:
            """Получение информации о кассе"""
            params = {
                "auth_login": self.auth_login,
                "auth_secret": self.auth_secret
            }

            return await self.utils.requestsApi("me", "info", params)

    class Method:
        def __init__(self, auth_login: str, auth_secret: str, utils: CrystalUtils):
            self.auth_login = auth_login
            self.auth_secret = auth_secret
            self.utils = utils

        async def getlist(self) -> Dict:
            """Получение информации о методах оплаты"""
            params = {
                "auth_login": self.auth_login,
                "auth_secret": self.auth_secret
            }

            return await self.utils.requestsApi("method", "list", params)

        async def edit(self, method: str, extra_commission_percent: float, enabled: bool) -> Dict:
            """Изменение настроек метода оплаты"""
            params = {
                "auth_login": self.auth_login,
                "auth_secret": self.auth_secret,
                "method": method,
                "extra_commission_percent": extra_commission_percent,
                "enabled": enabled
            }

            return await self.utils.requestsApi("method", "edit", params)

    class Balance:
        def __init__(self, auth_login: str, auth_secret: str, utils: CrystalUtils):
            self.auth_login = auth_login
            self.auth_secret = auth_secret
            self.utils = utils

        async def getinfo(self, hide_empty: bool = False) -> Dict:
            """Получение баланса кассы"""
            params = {
                "auth_login": self.auth_login,
                "auth_secret": self.auth_secret,
                "hide_empty": hide_empty
            }

            response = await self.utils.requestsApi("balance", "info", params)
            return response.get("balances", {})

    class Invoice:
        def __init__(self, auth_login: str, auth_secret: str, utils: CrystalUtils):
            self.auth_login = auth_login
            self.auth_secret = auth_secret
            self.utils = utils

        async def getinfo(self, id: str) -> Dict:
            """Получение информации о счёте"""
            params = {
                "auth_login": self.auth_login,
                "auth_secret": self.auth_secret,
                "id": id
            }

            return await self.utils.requestsApi("invoice", "info", params)

        async def create(self, amount: float, type_: str, lifetime: int, **kwargs) -> Dict:
            """Выставление счёта на оплату"""
            base_params = {
                "auth_login": self.auth_login,
                "auth_secret": self.auth_secret,
                "amount": amount,
                "type": type_,
                "lifetime": lifetime
            }

            params = self.utils.concatParams(base_params, kwargs)
            return await self.utils.requestsApi("invoice", "create", params)

    class Payoff:
        def __init__(self, auth_login: str, auth_secret: str, salt: str, utils: CrystalUtils):
            self.auth_login = auth_login
            self.auth_secret = auth_secret
            self.salt = salt
            self.utils = utils

        def _generate_signature(self, *args) -> str:
            """Генерация подписи для запросов"""
            signature_string = ":".join(str(arg) for arg in args)
            return hashlib.sha1(signature_string.encode()).hexdigest()

        async def create(self, amount: float, method: str, wallet: str, subtract_from: str, **kwargs) -> Dict:
            """Создание заявки на вывод средств"""
            signature = self._generate_signature(amount, method, wallet, self.salt)

            base_params = {
                "auth_login": self.auth_login,
                "auth_secret": self.auth_secret,
                "signature": signature,
                "amount": amount,
                "method": method,
                "wallet": wallet,
                "subtract_from": subtract_from
            }

            params = self.utils.concatParams(base_params, kwargs)
            return await self.utils.requestsApi("payoff", "create", params)

        async def submit(self, id: str) -> Dict:
            """Подтверждение заявки на вывод средств"""
            signature = self._generate_signature(id, self.salt)

            params = {
                "auth_login": self.auth_login,
                "auth_secret": self.auth_secret,
                "signature": signature,
                "id": id
            }

            return await self.utils.requestsApi("payoff", "submit", params)

        async def cancel(self, id: str) -> Dict:
            """Отмена заявки на вывод средств"""
            signature = self._generate_signature(id, self.salt)

            params = {
                "auth_login": self.auth_login,
                "auth_secret": self.auth_secret,
                "signature": signature,
                "id": id
            }

            return await self.utils.requestsApi("payoff", "cancel", params)

        async def getinfo(self, id: str) -> Dict:
            """Получение информации о заявке на вывод средств"""
            params = {
                "auth_login": self.auth_login,
                "auth_secret": self.auth_secret,
                "id": id
            }

            return await self.utils.requestsApi("payoff", "info", params)

    class Ticker:
        def __init__(self, auth_login: str, auth_secret: str, utils: CrystalUtils):
            self.auth_login = auth_login
            self.auth_secret = auth_secret
            self.utils = utils

        async def getlist(self) -> Dict:
            """Получение информации о заявке на вывод средств"""
            params = {
                "auth_login": self.auth_login,
                "auth_secret": self.auth_secret
            }

            response = await self.utils.requestsApi("ticker", "list", params)
            return response.get("tickers", {})

        async def get(self, tickers: str) -> Dict:
            """Получение курса валют по отношению к рублю"""
            params = {
                "auth_login": self.auth_login,
                "auth_secret": self.auth_secret,
                "tickers": tickers
            }

            return await self.utils.requestsApi("ticker", "get", params)


# Пример использования
async def crystal_create_link(callback: CallbackQuery, amount, currency: str, days: int):
    # Инициализация
    crystal = CrystalPAY(secrets.get('crystal_login'), secrets.get('crystal_secret'), secrets.get('crystal_salt'))

    # Пример асинхронного вызова
    try:
        # Получение информации о кассе
        me_info = await crystal.Me.getinfo()
        print("Me info:", me_info)

        # Получение баланса
        balance = await crystal.Balance.getinfo()
        print("Balance:", balance)

        # Создание инвойса
        invoice = await crystal.Invoice.create(
            amount=amount,
            type_=InvoiceType.purchase,
            lifetime=3600,
            description="Test invoice",
            amount_currency=currency,
            callback_url=f"{secrets.get('crystal_webhook')}",
        )
        print("Invoice:", invoice)
        print(invoice["id"])
        print(invoice["url"])
        if invoice["id"]:
            await rq.create_transaction(user_tg_id=callback.from_user.id,
                                        user_transaction=invoice["id"],
                                        username=callback.from_user.username,
                                        days=days)
            return invoice["url"]
        else:
            return 'CrystalPay api error'

    except Exception as e:
        print(f"Error: {e}")


async def payment_webhook_handler(request: Request, background_tasks: BackgroundTasks):
    try:
        payment_data = await request.json()
        # Получаем данные платежа
        logging.info(f"Получен платежный вебхук: {payment_data}")
        print('Webbhook получен')
        print(request.headers)
        if payment_data["state"] == "payed":
            print(payment_data)
            # Генерация хеша
            hash_string = f"{payment_data['id']}:{secrets.get('crystal_salt')}"
            computed_hash = hashlib.sha1(hash_string.encode()).hexdigest()
            # Безопасное сравнение подписи
            if not hmac.compare_digest(computed_hash, payment_data['signature']):
                print("Invalid signature!")
                return {"status": "received", "message": "Payment status is not CONFIRMED"}
            else:
                print("Signature is valid!")
                print('Оплата подтверждена')
                print(f'ID транзакции - {payment_data["id"]}')
                background_tasks.add_task(payment_process_background, f"{payment_data['id']}")
                return {"status": "success"}

    except Exception as e:
        logging.error(f"Ошибка обработки платежа: {e}")
        return {"status": "error", "message": str(e)}
