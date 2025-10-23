import hashlib
import json
import logging
import os
import uuid
import app.handlers.tools as tools
from pydantic import BaseModel
from app.settings import bot

import app.database.requests as rq

from app.settings import secrets

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

JSON_PATH = os.path.join(os.path.dirname(__file__), '..', '..', 'dig_data.json')


class DigisellerResponse(BaseModel):
    id: str
    inv: int
    goods: str
    error: str


def generate_signature(id_value, inv_value, password, model: str = "md5"):
    """
    Формирует MD5-подпись с автоматическим преобразованием типов
    """
    # Преобразуем все значения в строки
    id_str = str(id_value) if id_value is not None else ""
    inv_str = str(inv_value) if inv_value is not None else ""
    password_str = str(password) if password is not None else ""
    if model == "md5":
        # Формируем строку для подписи
        signature_string = f"{id_str}:{inv_str}:{password_str}"
        # Вычисляем MD5
        return hashlib.md5(signature_string.encode('utf-8')).hexdigest()
    if model == 'sha256':
        signature_string = f"{id_str};{inv_str};{password_str}"
        return hashlib.sha256(signature_string.encode('utf-8')).hexdigest()
    else:
        return None

def get_variant_info(json_file_path, merchant_id, variant_id, field=None):
    try:
        with open(json_file_path, 'r', encoding='utf-8') as file:
            data = json.load(file)

        variant_id_str = str(variant_id)
        variant_info = data['var_ids'][f'{merchant_id}']['variants'].get(variant_id_str)

        if variant_info is None:
            return None

        return variant_info if field is None else variant_info.get(field)

    except Exception as e:
        print(f"Произошла ошибка: {e}")
        return None


def extract_dig_items(secrets_in):
    result = {}
    index = 0
    while True:
        key = f"dig_item_id_{index}"
        value = secrets_in.get(key)
        if value is None:
            break
        result[index] = value
        index += 1
    return result


def check_id_exists_efficient(target_id, secrets_in):
    dig_items = extract_dig_items(secrets_in)
    values_set = set(dig_items.values())
    return str(target_id) in values_set


async def payment_async_logic(payment_data):
    logging.info(f"Получен вебхук от магазина: {payment_data}")
    # Проверяем обязательные поля
    if 'id' not in payment_data or 'inv' not in payment_data or 'options' not in payment_data:
        error_response = {
            "id": "",
            "inv": 0,
            "goods": "",
            "error": "Missing required fields: id, inv or options"
        }
        return 400
    if check_id_exists_efficient(payment_data['id'], secrets):
        # if payment_data['id'] == secrets.get('dig_item_id'):
        print('Id магазина обнаружен')
        order_id_check = await rq.get_full_transaction_info(payment_data["inv"])
        user_info = await tools.get_user_info("dig_id" + payment_data["inv"])
        # if order_id_check is None:
        if user_info == 404:
            print('Регистрация новой транзакции')
            merchant_id = payment_data['options'][0]['id']
            tariff_id = payment_data['options'][0]['user_data']
            days = get_variant_info(JSON_PATH, merchant_id, tariff_id, 'days')
            sign = generate_signature(payment_data['id'], payment_data['inv'], secrets.get('dig_pass'))
            print(sign)
            print(payment_data.get('sign'))
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
                await bot.send_message(chat_id=secrets.get('admin_id'),
                                       text=f"<b>Digiseller Order</b>\n\n"
                                            f"<b>Id </b>{payment_data['inv']}\n"
                                            f"<b>Days </b>{days}\n"
                                            f"<b>UserId </b>{usrid}\n"
                                            f"<b>Link </b><code>{buyer_nfo['subscription_url']}</code>",
                                       parse_mode="HTML")
                return buyer_nfo['subscription_url']
            else:
                return 400
        else:
            return user_info['subscription_url']


async def payment_async_logic_ggsell(payment_data):
    logging.info(f"Получен вебхук от магазина: {payment_data}")
    await bot.send_message(chat_id=secrets.get('admin_id'),
                           text=f"<b>GGSEL WEBHOOK:</b>\n\n"
                                f"<b>Content: \n</b><code>{payment_data}</code>",
                           parse_mode="HTML")
    # Проверяем обязательные поля
    if 'ID_I' not in payment_data or 'AMOUNT' not in payment_data or 'SHA256' not in payment_data:
        if 'product' not in payment_data:
            print('Bad request missing fields')
            return 400
        else:
            print('Availability check for product id request')
            print(payment_data['product']['id'])
            if check_id_exists_efficient(payment_data['product']['id'], secrets):
                # if payment_data['id'] == secrets.get('dig_item_id'):
                print('Id магазина обнаружен')
                print(payment_data)
                return 200
            else:
                print('ERROR - product id not found')
                return 400
    else:
        order_id_check = await rq.get_full_transaction_info(payment_data["ID_I"])
        user_info = await tools.get_user_info("gg_id" + payment_data["ID_I"])
        # if order_id_check is None:
        if user_info == 404:
            print('Регистрация новой транзакции')
            amount = payment_data['AMOUNT']
            print('Payed amount: ' + str(amount))
            # КОСТЫЛЬ РАСЧЕТА ДНЕЙ ПО СУММЕ (ЖДЕМ ФИКСА ОТ GGSELL)
            if amount > 90 < 250:
                days = 30
            elif amount >= 250 < 600:
                days = 90
            elif amount >= 600 < 1200:
                days = 180
            elif amount >= 1200:
                days = 365
            else:
                days = 7
            # ПИЗДЕЦ КОРОЧЕ - ЖДЕМ ФИКСА ОТ GGSELL
            # ПОДПИСЬ GGSELL (КРИВОЙ API С КРИВЫМ ОПИСАНИЕМ - ЖДЕМ ФИКСА)
            # sign = generate_signature('unique_code_заказа', payment_data['ID_I'], payment_data['ID_D'], 'sha256')
            # print(sign)
            # print(payment_data.get('SHA256'))
            # if payment_data.get('SHA256') == sign:
                # print('Подпись подтверждена')
            usrid = uuid.uuid4()
            buyer_nfo = await tools.add_new_user_info(
                    "gg_id" + payment_data["ID_I"],
                    usrid,
                    limit=0,
                    res_strat="no_reset",
                    expire_days=days
                )
            await rq.set_user(int("99"+payment_data["ID_I"]))
            await rq.create_transaction(user_tg_id=int("99"+payment_data["ID_I"]),
                                            user_transaction=f"{usrid}",
                                            username="gg_id" + payment_data["ID_I"],
                                            days=days)
            print('Отправка ссылки на подписку')
            print(buyer_nfo['subscription_url'])
            await bot.send_message(chat_id=secrets.get('admin_id'),
                                       text=f"<b>Digiseller Order</b>\n\n"
                                            f"<b>Id </b>{payment_data['ID_I']}\n"
                                            f"<b>Days </b>{days}\n"
                                            f"<b>UserId </b>{usrid}\n"
                                            f"<b>Link </b><code>{buyer_nfo['subscription_url']}</code>",
                                       parse_mode="HTML")
            return buyer_nfo['subscription_url']
            # else:
                # return 400
        else:
            return user_info['subscription_url']


async def payment_async_logic_new(payment_data):
    logging.info(f"Получен вебхук от магазина: {payment_data}")
    # Проверяем обязательные поля
    if 'id' not in payment_data or 'inv' not in payment_data or 'options' not in payment_data:
        error_response = {
            "id": "",
            "inv": 0,
            "goods": "",
            "error": "Missing required fields: id, inv or options"
        }
        return 400
    if check_id_exists_efficient(payment_data['id'], secrets):
        # if payment_data['id'] == secrets.get('dig_item_id'):
        print('Id магазина обнаружен')
        order_id_check = await rq.get_full_transaction_info(payment_data["inv"])
        user_info = await tools.get_user_info("dig_id" + payment_data["inv"])
        # if order_id_check is None:
        if user_info == 404:
            print('Регистрация новой транзакции')
            merchant_id = payment_data['options'][0]['id']
            tariff_id = payment_data['options'][0]['user_data']
            days = get_variant_info(JSON_PATH, merchant_id, tariff_id, 'days')
            sign = generate_signature(payment_data['id'], payment_data['inv'], secrets.get('dig_pass'))
            print(sign)
            print(payment_data.get('sign'))
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
                await bot.send_message(chat_id=secrets.get('admin_id'),
                                       text=f"<b>Digiseller Order</b>\n\n"
                                            f"<b>Id </b>{payment_data['inv']}\n"
                                            f"<b>Days </b>{days}\n"
                                            f"<b>UserId </b>{usrid}\n"
                                            f"<b>Link </b><code>{buyer_nfo['subscription_url']}</code>",
                                       parse_mode="HTML")
                return buyer_nfo['subscription_url']
            else:
                return 400
        else:
            return user_info['subscription_url']
