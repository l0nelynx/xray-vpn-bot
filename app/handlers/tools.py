import logging
import time
from aiogram import F, Router
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command, CommandObject
from aiogram.types import LabeledPrice, PreCheckoutQuery
from app.settings import bot, cp
from app.handlers.events import start_bot, stop_bot, userlist
from app.utils import check_amount
from app.handlers.events import main_menu, main_call
from app.locale.lang_ru import text_help
import app.database.requests as rq
import app.marzban.marzban as mz
from app.keyboards import payment_keyboard
import app.keyboards as kb
from app.settings import Secrets


async def success_payment_handler(message: Message):
    await message.answer(text="🥳Оплата прошла успешно!🤗")
    async with mz.MarzbanAsync() as marz:
        # await message.answer('Бесплатная версия (5 Гб в месяц)')
        user_info = await marz.get_user(name=message.from_user.username)
        if user_info == 404:
            print(user_info)
            buyer_nfo = await marz.add_user(
                template=mz.vless_template,
                name=f"{message.from_user.username}",
                usrid=f"{message.from_user.id}",
                limit=0,
                res_strat="no_reset",  # no_reset day week month year
                expire=(int(time.time()+30*24*60*60))
            )
            expire_day = round((buyer_nfo["expire"] - time.time()) / (24 * 60 * 60))
            sub_link = buyer_nfo["subscription_url"]
            await message.answer(text=f"❤️Cпасибо за покупку!\n\n"
                                      f"<b>Подписка оформлена</b>\n"
                                      f"Подписка будет действовать дней: {expire_day}\n"
                                      f"Ваша ссылка для подключения:\n"
                                      f"<code>{sub_link}</code>",parse_mode="HTML", reply_markup=kb.connect(sub_link))
        else:
            print(user_info["username"])
            sub_link = user_info["subscription_url"]
            status = user_info["status"]
            limit = user_info["data_limit"]
            expire_day = round((user_info["expire"] - time.time()) / (24 * 60 * 60))
            if status == "active" and limit is None:
                buyer_nfo = await marz.set_user(
                    template=mz.vless_template,
                    name=f"{message.from_user.username}",
                    limit=0,
                    res_strat="no_reset",  # no_reset day week month year
                    expire=(int(time.time()+(expire_day+30)*24*60*60))
                )
                await message.answer(text=f"❤️Cпасибо за покупку!\n\n"
                                          f"<b>Подписка успешно продлена еще на месяц</b>\n"
                                          f"Осталось дней: {expire_day+30}\n"
                                          f"Ваша ссылка для подключения:\n"
                                          f"<code>{sub_link}</code>",parse_mode="HTML", reply_markup=kb.connect(sub_link))

            else:
                buyer_nfo = await marz.set_user(
                    template=mz.vless_template,
                    name=f"{message.from_user.username}",
                    limit=0,
                    res_strat="no_reset",  # no_reset day week month year
                    expire=(int(time.time()+30*24*60*60))
                )
                await message.answer(text=f"❤️Cпасибо за покупку!\n\n"
                                          f"<b>Подписка обновлена</b>\n"
                                          f"Осталось дней: {30}\n"
                                          f"Ваша ссылка для подключения:\n"
                                          f"<code>{sub_link}</code>",parse_mode="HTML", reply_markup=kb.connect(sub_link))