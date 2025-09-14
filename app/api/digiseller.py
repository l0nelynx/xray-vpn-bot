import hashlib
import hmac
import json
import logging
import os
import uuid
import app.handlers.tools as tools
import sys
from typing import Dict
from fastapi import Response
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
        logging.info(f"Получен вебхук от магазина: {payment_data}")

        # Проверяем обязательные поля
        if 'id' not in payment_data or 'inv' not in payment_data or 'options' not in payment_data:
            error_response = {
                "id": "",
                "inv": 0,
                "goods": "",
                "error": "Missing required fields: id, inv or options"
            }
            return Response(
                content=json.dumps(error_response),
                media_type="application/json",
                status_code=400
            )

        if payment_data['id'] == secrets.get('dig_item_id'):
            print('Id магазина обнаружен')
            order_id_check = await rq.get_full_transaction_info(payment_data["inv"])

            if order_id_check is None:
                print('Регистрация новой транзакции')
                tariff_id = payment_data['options'][0]['user_data']
                days = get_variant_info(JSON_PATH, tariff_id, 'days')
                sign = generate_signature(payment_data['id'], payment_data['inv'], secrets.get('dig_pass'))

                if payment_data.get('sign') == sign:
                    print('Подпись подтверждена')
                    usrid = uuid.uuid4()
                    buyer_nfo = await tools.add_new_user_info(
                        "dig_id" + payment_data["inv"],
                        usrid,
                        limit=0,
                        res_strat="no_reset",
                        expire_days=days
                    )
                    await rq.set_user(int(payment_data["inv"]))
                    await rq.create_transaction(user_tg_id=int(payment_data["inv"]),
                                                user_transaction=f"{usrid}",
                                                username="dig_id" + payment_data["inv"],
                                                days=days)

                    print('Отправка ссылки на подписку')
                    print(buyer_nfo['subscription_url'])
                    success_response = {
                        "id": payment_data['id'],
                        "inv": int(payment_data['inv']),  # Преобразуем в int как требуется
                        "goods": buyer_nfo['subscription_url'],
                        "error": ""
                    }

                    return Response(
                        media_type="application/json",
                        content=json.dumps(success_response),
                        status_code=500
                    )
                else:
                    error_response = {
                        "id": payment_data['id'],
                        "inv": int(payment_data['inv']),
                        "goods": "",
                        "error": "Invalid signature"
                    }
                    return Response(
                        content=json.dumps(error_response),
                        media_type="application/json",
                        status_code=400
                    )
            else:
                error_response = {
                    "id": payment_data['id'],
                    "inv": int(payment_data['inv']),
                    "goods": "",
                    "error": "Order already processed"
                }
                return Response(
                    content=json.dumps(error_response),
                    media_type="application/json",
                    status_code=400
                )
        else:
            error_response = {
                "id": "",
                "inv": 0,
                "goods": "",
                "error": "Invalid item ID"
            }
            return Response(
                content=json.dumps(error_response),
                media_type="application/json",
                status_code=400
            )

    except Exception as e:
        logging.error(f"Ошибка обработки платежа: {e}")

        return Response(
            media_type="application/json",
            status_code=500
        )



# async def payment_webhook_handler(request: Request, response: Response):
#     try:
#         payment_data = await request.json()
#         # Получаем данные платежа
#         logging.info(f"Получен вебхук от магазина: {payment_data}")
#         print('REQUEST HEADERS:')
#         print(request.headers)
#         print('____________DATA PROCESSING______________')
#         print(payment_data['id'])
#         print(secrets.get('dig_item_id'))
#         if payment_data['id'] == secrets.get('dig_item_id'):
#             order_id_check = await rq.get_full_transaction_info(payment_data["inv"])
#             print(f'Наличие заказа в БД:{order_id_check}')
#             if order_id_check is None:
#                 print('В списке обработанных заказов - заказа нет')
#                 tariff_id = payment_data['options'][0]['user_data']
#                 print(tariff_id)
#                 print(JSON_PATH)
#                 days = get_variant_info(JSON_PATH, tariff_id, 'days')
#                 sign = generate_signature(payment_data['id'], payment_data['inv'], secrets.get('dig_pass'))
#                 if payment_data['sign'] == sign:
#                     usrid = uuid.uuid4()
#                     buyer_nfo = await tools.add_new_user_info("dig_id" + payment_data["inv"],
#                                                               usrid,
#                                                               limit=0,
#                                                               res_strat="no_reset",
#                                                               expire_days=days)
#                     print(buyer_nfo['subscription_url'])
#                     success_response = {
#                         "status": "success",
#                         "message": "error",
#                         "id": payment_data['id'],
#                         "inv": f"{payment_data['inv']}",
#                         "goods": f"{buyer_nfo['subscription_url']}",
#                         "error": ""
#                     }
#                     response_payload = {
#                         "headers": {
#                             "Content-Type": "application/json"
#                         },
#                         "body": success_response
#                     }
#                     print(success_response)
#                     # response.status_code = 200
#                     response.body = success_response
#                     return response
#                 else:
#                     return 400
#             else:
#                 return 400
#         else:
#             return 400
#     except Exception as e:
#         logging.error(f"Ошибка обработки платежа: {e}")
#         return {"status": "error", "message": str(e)}
