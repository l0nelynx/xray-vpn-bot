import logging

from app.settings import bot, secrets

import app.database.requests as rq
import app.keyboards as kb
import app.handlers.tools as tools

from fastapi import Request, BackgroundTasks

pt_key = secrets.get('platega_api_key')
pt_id = secrets.get('platega_merchant_id')


# 2. Вебхук для подтверждения платежей
async def payment_webhook_handler(request: Request, background_tasks: BackgroundTasks):
    try:
        payment_data = await request.json()
        # Получаем данные платежа
        logging.info(f"Получен платежный вебхук: {payment_data}")
        print('Webbhook получен')
        print(request.headers)
        if request.headers.get("X-MerchantId") == pt_id and request.headers.get("X-Secret") == pt_key:
            print(payment_data)
            if payment_data['status'] == "CONFIRMED":
                print('Оплата подтверждена')
                print(f'ID транзакции - {payment_data["id"]}')
                background_tasks.add_task(payment_process_background, payment_data)
                return {"status": "success"}
            else:
                return {"status": "received", "message": "Payment status is not CONFIRMED"}
    except Exception as e:
        logging.error(f"Ошибка обработки платежа: {e}")
        return {"status": "error", "message": str(e)}


async def payment_process_background(payment_data: dict):
    userdata = await rq.get_full_transaction_info(payment_data['id'])
    usrid = userdata["user_tg_id"]
    usrname = userdata["username"]
    tariff_days = 30  # Take from db here
    if userdata['status'] == 'created':
        await bot.send_message(chat_id=secrets.get('admin_id'),
                               text=f"Транзакция ID - {payment_data['id']}")
        await rq.update_order_status(payment_data['id'], 'confirmed')
        print(f'UserId - {userdata["user_tg_id"]}')
        await bot.send_message(chat_id=usrid, text='Успешная покупка!')
        await bot.send_message(chat_id=usrid, text="🥳Оплата прошла успешно!🤗")
        user_info = await tools.get_user_info(usrname)
        if user_info == 404:
            # print(user_info)
            print("Пользователь не найден - создание нового согласно тарифу")
            buyer_nfo = await tools.add_new_user_info(usrname,
                                                      usrid,
                                                      limit=0,
                                                      res_strat="no_reset",
                                                      expire_days=tariff_days)
            expire_day = await tools.get_user_days(buyer_nfo)
            sub_link = buyer_nfo["subscription_url"]
            await bot.send_message(chat_id=usrid, text=f"❤️Cпасибо за покупку!\n\n"
                                                       f"<b>Подписка оформлена</b>\n"
                                                       f"Подписка будет действовать дней: {expire_day}\n"
                                                       f"Ваша ссылка для подключения:\n"
                                                       f"<code>{sub_link}</code>", parse_mode="HTML",
                                   reply_markup=kb.connect(sub_link))
        else:
            print("User found setting up new user info")
            sub_link = user_info["subscription_url"]
            status = user_info["status"]
            limit = user_info["data_limit"]
            if user_info["expire"] is None:
                expire_day = "Unlimited"
            else:
                expire_day = await tools.get_user_days(user_info)
            if status == "active" and limit is None:
                buyer_nfo = await tools.set_user_info(usrid,
                                                      limit=0,
                                                      res_strat='no_reset',
                                                      expire_days=(expire_day + tariff_days))
                expire_day = expire_day + tariff_days
                await bot.send_message(chat_id=usrid, text=f"❤️Cпасибо за покупку!\n\n"
                                                           f"<b>Подписка успешно продлена еще на месяц</b>\n"
                                                           f"Осталось дней: {expire_day}\n"
                                                           f"Ваша ссылка для подключения:\n"
                                                           f"<code>{sub_link}</code>", parse_mode="HTML",
                                       reply_markup=kb.connect(sub_link))

            else:
                buyer_nfo = await tools.set_user_info(usrid,
                                                      limit=0,
                                                      res_strat="no_reset",
                                                      expire_days=tariff_days)
                expire_day = await tools.get_user_days(buyer_nfo)
                sub_link = buyer_nfo["subscription_url"]
                await bot.send_message(chat_id=usrid, text=f"❤️Cпасибо за покупку!\n\n"
                                                           f"<b>Подписка обновлена</b>\n"
                                                           f"Осталось дней: {expire_day}\n"
                                                           f"Ваша ссылка для подключения:\n"
                                                           f"<code>{sub_link}</code>", parse_mode="HTML",
                                       reply_markup=kb.connect(sub_link))
