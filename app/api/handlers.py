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


async def payment_process_background(order_id: str):
    userdata = await rq.get_full_transaction_info(order_id)
    usrid = userdata["user_tg_id"]
    usrname = userdata["username"]
    tariff_days = 30  # Take from db here
    if userdata['status'] == 'created':
        await bot.send_message(chat_id=secrets.get('admin_id'),
                               text=f"Транзакция ID - {order_id}")
        await rq.update_order_status(order_id, 'confirmed')
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
                buyer_nfo = await tools.set_user_info(usrname,
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
                buyer_nfo = await tools.set_user_info(usrname,
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
