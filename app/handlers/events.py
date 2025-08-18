import os
import asyncio
from app.settings import bot, secrets
from app.views import start_bot_msg, stop_bot_msg
from app.database.models import async_main
from app.settings import run_webserver
import app.keyboards as kb
import app.database.requests as rq
import app.locale.lang_ru as ru

lang = eval(f"{secrets.get('language')}")
crypto = secrets.get('crypto')


async def start_bot():
    await bot.send_message(secrets.get('admin_id'), start_bot_msg())
    await async_main()  # Создание таблиц БД при запуске



async def userlist():
    all_users = await rq.get_users()
    usrids = ""
    for User in all_users:
        if len(usrids) >= 3000:
            return
        else:
            usrids = f"{usrids}\n{User.tg_id}"
    await bot.send_message(chat_id=secrets.get('admin_id'), text=usrids)


async def stop_bot():
    await bot.send_message(secrets.get('admin_id'), stop_bot_msg())


async def main_menu(message, menu_type):
    if menu_type == "pro":
        await message(lang.start_pro+lang.start_agreement, reply_markup=kb.main_pro, parse_mode="HTML")
    elif menu_type == "free":
        await message(lang.start_free+lang.start_agreement, reply_markup=kb.main_free, parse_mode="HTML")
    else:
        await message(lang.start_base+lang.start_new+lang.start_agreement, reply_markup=kb.main_new, parse_mode="HTML")


async def main_call(message, menu_type):
    await main_menu(message, menu_type)
