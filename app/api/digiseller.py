import hashlib
import hmac
import json
import logging
import os
import uuid
import app.handlers.tools as tools
import sys
from typing import Dict

import aiohttp
from aiogram.types import CallbackQuery
from fastapi import Request, BackgroundTasks

import app.database.requests as rq
from app.api.handlers import payment_process_background
from app.settings import secrets

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

JSON_PATH = os.path.join(os.path.dirname(__file__), '..', '..', 'dig_data.json')


def generate_signature(id_value, inv_value, password):
    """
    Формирует MD5-подпись с автоматическим преобразованием типов
    """
    # Преобразуем все значения в строки
    id_str = str(id_value) if id_value is not None else ""
    inv_str = str(inv_value) if inv_value is not None else ""
    password_str = str(password) if password is not None else ""

    # Формируем строку для подписи
    signature_string = f"{id_str}:{inv_str}:{password_str}"

    # Вычисляем MD5
    return hashlib.md5(signature_string.encode('utf-8')).hexdigest()


def get_variant_info(json_file_path, variant_id, field=None):
    """
    Получает информацию о варианте по ID

    Args:
        json_file_path (str): Путь к JSON-файлу
        variant_id (str/int): ID варианта
        field (str, optional): Конкретное поле для получения (если None, возвращает весь объект)

    Returns:
        dict/int/str: Запрошенная информация или None, если вариант не найден
    """
    try:
        with open(json_file_path, 'r', encoding='utf-8') as file:
            data = json.load(file)

        variant_id_str = str(variant_id)
        variant_info = data['var_ids']['variants'].get(variant_id_str)

        if variant_info is None:
            return None

        return variant_info if field is None else variant_info.get(field)

    except Exception as e:
        print(f"Произошла ошибка: {e}")
        return None


async def payment_webhook_handler(request: Request):
    try:
        payment_data = await request.json()
        # Получаем данные платежа
        logging.info(f"Получен вебхук от магазина: {payment_data}")
        print('REQUEST HEADERS:')
        print(request.headers)
        print('____________DATA PROCESSING______________')
        print(payment_data['id'])
        print(secrets.get('dig_item_id'))
        if payment_data['id'] == secrets.get('dig_item_id'):
            order_id_check = await rq.get_full_transaction_info(payment_data["inv"])
            print(f'Наличие заказа в БД:{order_id_check}')
            if order_id_check is None:
                print('В списке обработанных заказов - заказа нет')
                tariff_id = payment_data['options'][0]['user_data']
                print(tariff_id)
                print(JSON_PATH)
                days = get_variant_info(JSON_PATH, tariff_id, 'days')
                sign = generate_signature(payment_data['id'], payment_data['inv'], secrets.get('dig_pass'))
                if payment_data['sign'] == sign:
                    usrid = uuid.uuid4()
                    buyer_nfo = await tools.add_new_user_info("dig_id"+payment_data["inv"],
                                                              usrid,
                                                              limit=0,
                                                              res_strat="no_reset",
                                                              expire_days=days)
                    print(buyer_nfo['subscription_url'])
                    success_response = {
                        # "status": "success",
                        "id": payment_data['id'],
                        "inv": f"{payment_data['inv']}",
                        "goods": f"{buyer_nfo['subscription_url']}",
                        "error": ""
                    }
                    response_payload = {
                            "headers": {
                                "Content-Type": "application/json"
                            },
                            "body": success_response
                        }
                    print(success_response)
                    return {"status": "error", "message": "bruh"}
    except Exception as e:
        logging.error(f"Ошибка обработки платежа: {e}")
        return {"status": "error", "message": str(e)}
