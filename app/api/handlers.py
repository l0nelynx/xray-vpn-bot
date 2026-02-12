import app.database.requests as rq
import app.handlers.tools as tools
import app.keyboards as kb
import app.marzban.templates as templates
import app.locale.lang_ru as ru
from app.settings import bot, secrets
import asyncio

async def send_alert(order_id: str, usrname: str, usrid: int, tariff_days: int):
    await bot.send_message(chat_id=secrets.get('admin_id'),
                           text=f"Транзакция ID - {order_id}\n"
                                f"Пользователь - @{usrname}\n"
                                f"UserId - {usrid}\n"
                                f"Количество дней - {tariff_days}\n")

async def create_subscription_for_order(user_info, usrname, usrid, tariff_days: int, template):
    if user_info == 404:
        print("Пользователь не найден - создание нового согласно тарифу")
        buyer_nfo = await tools.add_new_user_info(usrname,
                                                  usrid,
                                                  limit=0,
                                                  res_strat="no_reset",
                                                  expire_days=tariff_days,
                                                  template=template)
        expire_day = await tools.get_user_days(buyer_nfo)
        sub_link = buyer_nfo["subscription_url"]
        await bot.send_message(chat_id=usrid, text=f"❤️Cпасибо за покупку!\n\n"
                                                   f"<b>Подписка оформлена</b>\n"
                                                   f"Подписка будет действовать дней: {expire_day}\n"
                                                   f"Ваша ссылка для подключения:\n"
                                                   f"<code>{sub_link}</code>", parse_mode="HTML",
                               reply_markup=kb.connect(sub_link))
        return 200
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
            buyer_nfo = await tools.set_user_info(name=usrname,
                                                  limit=0,
                                                  res_strat='no_reset',
                                                  expire_days=(expire_day + tariff_days),
                                                  template=template)
            expire_day = expire_day + tariff_days
            await bot.send_message(chat_id=usrid, text=f"❤️Cпасибо за покупку!\n\n"
                                                       f"<b>Подписка успешно продлена еще на месяц</b>\n"
                                                       f"Осталось дней: {expire_day}\n"
                                                       f"Ваша ссылка для подключения:\n"
                                                       f"<code>{sub_link}</code>", parse_mode="HTML",
                                   reply_markup=kb.connect(sub_link))
            return 200
        else:
            buyer_nfo = await tools.set_user_info(name=usrname,
                                                  limit=0,
                                                  res_strat="no_reset",
                                                  expire_days=tariff_days,
                                                  template=template)
            expire_day = await tools.get_user_days(buyer_nfo)
            sub_link = buyer_nfo["subscription_url"]
            await bot.send_message(chat_id=usrid, text=f"❤️Cпасибо за покупку!\n\n"
                                                       f"<b>Подписка обновлена</b>\n"
                                                       f"Осталось дней: {expire_day}\n"
                                                       f"Ваша ссылка для подключения:\n"
                                                       f"<code>{sub_link}</code>", parse_mode="HTML",
                                   reply_markup=kb.connect(sub_link))
            return 200


async def payment_process_background(order_id: str):
    userdata = await rq.get_full_transaction_info(order_id)
    usrid = userdata["user_tg_id"]
    usrname = userdata["username"]
    tariff_days = userdata["days_ordered"]  # Take from db here
    if userdata['status'] == 'created':
        await send_alert(order_id, usrname, usrid, tariff_days)
        await rq.update_order_status(order_id, 'confirmed')
        user_info = await tools.get_user_info(usrname)
        delivery_status = await create_subscription_for_order(user_info, usrname, usrid, tariff_days, templates.vless_premium)
        if delivery_status != 200:
            unsuccess_counter = 0
            while unsuccess_counter <= 3:
                print('Ошибка при доставке товара, попытка повторить доставку')
                delivery_status = await create_subscription_for_order(user_info, usrname, usrid, tariff_days,
                                                                      templates.vless_premium)
                if delivery_status == 200:
                    print('Доставка прошла успешно')
                    unsuccess_counter = 5
                    break
                else:
                    unsuccess_counter += 1
                    await asyncio.sleep(2)
                    print(f'Попытка доставки #{unsuccess_counter} не удалась')

    else:
        print('Double webhook detected')
