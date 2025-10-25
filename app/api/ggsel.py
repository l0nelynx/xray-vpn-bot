import http.client
import asyncio
import json
import time
import hashlib
import uuid
from app.settings import bot
import app.handlers.tools as tools
from app.settings import secrets
from app.api.digiseller import get_variant_info, JSON_PATH
import app.database.requests as rq

conn = http.client.HTTPSConnection("seller.ggsel.net")

async def get_token():
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
    conn.request("POST", "/api_sellers/api/apilogin", payload, headers)
    res = conn.getresponse()
    data = res.read()
    print(data.decode("utf-8"))
    data = json.loads(data.decode("utf-8"))
    return data['token']

async def send_message(id_i: int, message: str, token: str):
    payload = json.dumps({
        "message": f"{message}"
    })
    headers = {
        'Content-Type': 'application/json'
    }
    conn.request("POST", f"/api_sellers/api/debates/v2?token={token}&id_i={id_i}", payload, headers)
    res = conn.getresponse()
    data = res.read()
    print(data.decode("utf-8"))

async def return_last_sales(top: int = 3, token: str = None):
    payload = ''
    headers = {
        'Accept': 'application/json',
        'locale': 'ru-RU'
    }
    conn.request("GET", f"/api_sellers/api/seller-last-sales?token={token}&seller_id={secrets.get('ggsel_seller_id')}&top={top}", payload, headers)
    res = conn.getresponse()
    status = res.status
    print(status)
    data = res.read()
    print(data.decode("utf-8"))
    # Формат принимаемых данных:
    # {
    #     "retval": 0,
    #     "retdesc": "string",
    #     "sales": [
    #         {
    #             "invoice_id": 0,
    #             "date": "string",
    #             "product": {
    #                 "id": 0,
    #                 "name": "string",
    #                 "price_rub": 0,
    #                 "price_usd": 0,
    #                 "price_eur": 0,
    #                 "price_uah": 0
    #             }
    #         }
    #     ]
    # }
    return json.loads(data.decode("utf-8"))

async def get_order_info(inv_id: int, token: str):
    payload = ''
    headers = {
        'Accept': 'application/json',
        'locale': 'ru-RU'
    }
    conn.request("GET", f"/api_sellers/api/purchase/info/{inv_id}?token={token}", payload, headers)
    res = conn.getresponse()
    data = res.read()
    print(data.decode("utf-8"))
    # Формат принимаемых данных:
    # {
    #     "retval": 0,
    #     "retdesc": "string",
    #     "content": {
    #         "item_id": 0,
    #         "content_id": 0,
    #         "cart_uid": "string",
    #         "name": "string",
    #         "amount": 0,
    #         "currency_type": "USD",
    #         "invoice_state": 0,
    #         "purchase_date": "2024-01-01T12:00:00Z",
    #         "date_pay": "2024-01-01T12:30:00Z",
    #         "agent_id": 0,
    #         "agent_percent": 0,
    #         "agent_fee": 0,
    #         "query_string": "string",
    #         "unit_goods": "string",
    #         "cnt_goods": "string",
    #         "promo_code": "string",
    #         "bonus_code": "string",
    #         "feedback": {
    #             "deleted": true,
    #             "feedback": "string",
    #             "feedback_type": "positive",
    #             "comment": "string"
    #         },
    #         "unique_code_state": {
    #             "state": 0,
    #             "date_check": "2024-07-29T15:51:28.071Z",
    #             "date_delivery": "2024-07-29T15:51:28.071Z",
    #             "date_confirmed": "2024-07-29T15:51:28.071Z",
    #             "date_refuted": "2024-07-29T15:51:28.071Z"
    #         },
    #         "options": [
    #             {
    #                 "id": 0,
    #                 "name": "string",
    #                 "user_data": "string",
    #                 "user_data_id": 0
    #             }
    #         ],
    #         "buyer_info": {
    #             "payment_method": "string",
    #             "account": "string",
    #             "email": "string",
    #             "phone": "string",
    #             "skype": "string",
    #             "whatsapp": "string",
    #             "ip_address": "string",
    #             "payment_aggregator": "string"
    #         },
    #         "owner": 0,
    #         "day_lock": 0,
    #         "lock_state": "free",
    #         "profit": 0,
    #         "external_order_id": "string"
    #     }
    # }
    return json.loads(data.decode("utf-8"))


async def create_subscription_for_order(content_id, days: int):
    usrid = uuid.uuid4()
    buyer_nfo = await tools.add_new_user_info(
        "gg_id" + content_id,
        usrid,
        limit=0,
        res_strat="no_reset",
        expire_days=days
    )
    await rq.set_user(int(content_id))
    await rq.create_transaction(user_tg_id=int(content_id),
                                user_transaction=f"{usrid}",
                                username="gg_id" + content_id,
                                days=days)
    print('Отправка ссылки на подписку')
    print(buyer_nfo['subscription_url'])
    await bot.send_message(chat_id=secrets.get('admin_id'),
                           text=f"<b>Digiseller Order</b>\n\n"
                                f"<b>Id </b>99{content_id}\n"
                                f"<b>Days </b>{days}\n"
                                f"<b>UserId </b>{usrid}\n"
                                f"<b>Link </b><code>{buyer_nfo['subscription_url']}</code>",
                           parse_mode="HTML")
    return buyer_nfo['subscription_url']


async def check_new_orders(top: int = 3, token: str = None):
    last_sales = await return_last_sales(top=top, token=token)
    for sale in last_sales['sales']:
        order_info = await get_order_info(sale['invoice_id'], token=token)
        if order_info['content']['invoice_state'] >= 3 <= 4:
            # Оплаченный заказ
            print(f"Оплаченный заказ #{order_info['content']['content_id']}\ninv_id: {sale['invoice_id']}\noption id: {order_info['content']['options'][0]['user_data_id']}")
            order_id_check = await rq.get_full_transaction_info_by_id(int("99" + order_info['content']['content_id']))
            if order_id_check is None:
                print('Найден новый оплаченный заказ, регистрация заказа')
                merchant_id = order_info['content']['options'][0]['id']
                tariff_id = order_info['content']['options'][0]['user_data_id']
                days = get_variant_info(JSON_PATH, merchant_id, tariff_id, 'days')
                await rq.set_user(int("99" + order_info['content']['content_id']))
                await rq.create_transaction(user_tg_id=int("99" + order_info['content']['content_id']),
                                            user_transaction=f"{order_info['content']['cart_uid']}",
                                            username="gg_id" + order_info['content']['content_id'],
                                            days=days)
                print('Заказ зарегистрирован в базе')
                link = await create_subscription_for_order(order_info['content']['content_id'],days)
                print('Подписка сформирована')
                await send_message(id_i=order_info['content']['content_id'],message=f'Ваша ключ-ссылка: {link}', token=token)
                print('Сообщение с товаром отправлено покупателю')
            else:
                print('Заказ уже зарегистрирован в базе')
        else:
            # Заказ оплачен
            print(f"Заказ оплачен: {sale['invoice_id']}")


async def order_delivery_loop():
    while True:
        # try:
            token = await get_token()
            await check_new_orders(top=3, token=token)
        # except Exception as e:
        #    print(f"Ошибка при проверке новых заказов: {e}")
            await asyncio.sleep(300)  # Проверять каждые 5 минут