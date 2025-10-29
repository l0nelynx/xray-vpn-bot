import aiohttp
import asyncio
import json
import time
import hashlib
import uuid
from app.settings import ggsel_bot as bot
# import app.handlers.tools as tools
from app.handlers.tools import get_user_info, add_new_user_info
from app.settings import secrets
# from backend import secrets
from app.api.digiseller import get_variant_info, JSON_PATH
import app.database.requests as rq

async def send_alert(message: str):
    await bot.send_message(chat_id=secrets.get('admin_id'),
                           text=f"<b>GGSel Alert</b>\n\n"
                                f"{message}",
                           parse_mode="HTML",
                           disable_notification=True)

async def get_token(session):
    timestamp = time.time()
    sign = f"{secrets.get('ggsel_api_key')}"+f"{timestamp}"
    sign = hashlib.sha256(sign.encode("utf-8")).hexdigest()
    payload = json.dumps({
      "seller_id": secrets.get("ggsel_seller_id"),
      "timestamp": timestamp,
      "sign": f"{sign}"
    })
    print(payload)
    headers = {
      'Content-Type': 'application/json',
      'Accept': 'application/json'
    }
    async with session.post("/api_sellers/api/apilogin",
                           data=payload, headers=headers) as response:
        data = await response.read()
        print(data.decode("utf-8"))
        data = json.loads(data.decode("utf-8"))
        return data['token']

async def send_message(session, id_i: int, message: str, token: str):
    payload = json.dumps({
        "message": f"{message}"
    })
    headers = {
        'Content-Type': 'application/json'
    }
    async with session.post(f"/api_sellers/api/debates/v2?token={token}&id_i={id_i}",
                           data=payload, headers=headers) as response:
        data = await response.read()
        print(data.decode("utf-8"))

async def return_last_sales(session, top: int = 3, token: str = None):
    headers = {
        'Accept': 'application/json',
        'locale': 'ru-RU'
    }
    async with session.get(f"/api_sellers/api/seller-last-sales?token={token}&seller_id={secrets.get('ggsel_seller_id')}&top={top}",
                          headers=headers) as response:
        status = response.status
        print(status)
        data = await response.read()
        print(data.decode("utf-8"))
        return json.loads(data.decode("utf-8"))

async def get_order_info(session, inv_id: int, token: str):
    headers = {
        'Accept': 'application/json',
        'locale': 'ru-RU'
    }
    async with session.get(f"/api_sellers/api/purchase/info/{inv_id}?token={token}",
                          headers=headers) as response:
        data = await response.read()
        print(data.decode("utf-8"))
        return json.loads(data.decode("utf-8"))

async def create_subscription_for_order(content_id, days: int):
    user_info = await get_user_info(f"gg_id{content_id}")
    if user_info == 404:
        usrid = uuid.uuid4()
        buyer_nfo = await add_new_user_info(
            f"gg_id{content_id}",
            usrid,
            limit=0,
            res_strat="no_reset",
            expire_days=days
        )
        print('Отправка ссылки на подписку')
        print(buyer_nfo['subscription_url'])
        await bot.send_message(chat_id=secrets.get('admin_id'),
                               text=f"<b>GGsel Order</b>\n\n"
                                    f"<b>GGsel Id: </b><code>{content_id}<code>\n"
                                    f"<b>Days: </b>{days}\n"
                                    f"<b>Vless uuid: </b>{usrid}\n"
                                    f"<b>Link: </b><code>{buyer_nfo['subscription_url']}</code>",
                               parse_mode="HTML")
        return buyer_nfo['subscription_url']
    else:
        print('Пользователь уже существует')
        return user_info['subscription_url']

async def check_new_orders(session, top: int = 3, token: str = None):
    last_sales = await return_last_sales(session, top=top, token=token)
    for sale in last_sales['sales']:
        order_id_check = await rq.get_user_by_tg_id(int(f"99{sale['invoice_id']}"))
        # print(int(f"99{sale['invoice_id']}"))
        # print(order_id_check)
        if order_id_check == 404:
            order_info = await get_order_info(session, sale['invoice_id'], token=token)
            if order_info['content']['invoice_state'] >= 3 <= 4:
                await rq.set_user(int(f"99{order_info['content']['content_id']}"))
                print(f"Оплаченный заказ #{order_info['content']['content_id']}\ninv_id: {sale['invoice_id']}\noption id: {order_info['content']['options'][0]['user_data_id']}")
                # await send_alert(f"Оплаченный заказ #{order_info['content']['content_id']}\ninv_id: {sale['invoice_id']}\noption id: {order_info['content']['options'][0]['user_data_id']}")
                # order_id_check = await rq.get_full_transaction_info_by_id(int(f"99{order_info['content']['content_id']}"))
                # if order_id_check is None:
                await send_alert('Найден новый оплаченный заказ, регистрация заказа')
                print('Найден новый оплаченный заказ, регистрация заказа')
                merchant_id = order_info['content']['options'][0]['id']
                tariff_id = order_info['content']['options'][0]['user_data_id']
                days = get_variant_info(JSON_PATH, merchant_id, tariff_id, 'days')
                await rq.create_transaction(user_tg_id=int(f"99{order_info['content']['content_id']}"),
                                                # user_transaction=f"{order_info['content']['cart_uid']}",
                                                user_transaction=f"{uuid.uuid4()}",
                                                username=f"99{order_info['content']['content_id']}",
                                                days=days)
                print('Заказ зарегистрирован в базе')
                link = await create_subscription_for_order(order_info['content']['content_id'],days)
                print('Подписка сформирована')
                await send_message(session, id_i=order_info['content']['content_id'],message=f'Спасибо за покупку!\nВаша ключ-ссылка: {link}', token=token)
                print('Сообщение с товаром отправлено покупателю')
            else:
                print(f"Заказ оплачен либо отменен: {sale['invoice_id']}")
                await rq.set_user(int(f"99{order_info['content']['content_id']}"))
        else:
            print('Заказ уже зарегистрирован в базе')

async def order_delivery_loop():
    async with aiohttp.ClientSession(base_url="https://seller.ggsel.net") as session:
        while True:
            error_counter = 0
            try:
                token = await get_token(session)
                await check_new_orders(session, top=secrets.get('ggsel_top_value'), token=token)
                error_counter = 0
            except Exception as e:
                error_counter += 1
                print(f"Ошибка при проверке новых заказов: {e}")
                if error_counter > secrets.get('ggsel_error_threshold'):
                    await send_alert(f"Ошибка при проверке новых заказов: {e}\n Неудачных запросов подряд: {error_counter}")
            await asyncio.sleep(secrets.get('ggsel_check_interval')*60)