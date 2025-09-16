import app.database.requests as rq
import app.keyboards as kb
import app.locale.lang_ru as ru
from app.database.models import async_main
from app.settings import bot, secrets
from app.views import start_bot_msg, stop_bot_msg
from io import BytesIO
from aiogram.types import BufferedInputFile

lang = eval(f"{secrets.get('language')}")
crypto = secrets.get('crypto')


async def start_bot():
    await bot.send_message(secrets.get('admin_id'), start_bot_msg())
    await async_main()  # Создание таблиц БД при запуске


async def userlist():
    all_users = await rq.get_users()
    i = 0
    usrids = f"| № | Tg_id "
    for User in all_users:
        usrids = f"{usrids}\n| {i} | {User.tg_id} |"
        i = i + 1
    file_bytes = usrids.encode('utf-8')
    file = BufferedInputFile(file_bytes, filename='users.txt')
    await bot.send_document(chat_id=secrets.get('admin_id'), document=file,
                            caption='Here is your userlist')


async def stop_bot():
    await bot.send_message(secrets.get('admin_id'), stop_bot_msg())


async def main_menu(message, menu_type):
    if menu_type == "pro":
        await message(lang.start_pro + lang.start_agreement, reply_markup=kb.main_pro, parse_mode="HTML")
    elif menu_type == "free":
        await message(lang.start_free + lang.start_agreement, reply_markup=kb.main_free, parse_mode="HTML")
    else:
        await message(lang.start_base + lang.start_new + lang.start_agreement, reply_markup=kb.main_new,
                      parse_mode="HTML")


async def main_call(message, menu_type):
    await main_menu(message, menu_type)
