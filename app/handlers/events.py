import os

from app.settings import bot, Secrets
from app.views import start_bot_msg, stop_bot_msg
from app.database.models import async_main
import app.keyboards as kb
import app.database.requests as rq


async def start_bot():
    await bot.send_message(Secrets.admin_id, start_bot_msg())
    await async_main()  # Создание таблиц БД при запуске


async def userlist():
    all_users = await rq.get_users()
    usrids = ""
    for User in all_users:
        if len(usrids) >= 3000:
            return
        else:
            usrids = f"{usrids}\n{User.tg_id}"
    await bot.send_message(chat_id=Secrets.admin_id, text=usrids)


async def stop_bot():
    await bot.send_message(Secrets.admin_id, stop_bot_msg())

crypto = os.environ["CRYPTO"]
text = ("<b>Быстрый, простой и удобный VPN в Telegram</b>\n\n"
        "🚀 <b>Высокая скорость, отсутствие рекламы</b>\n"
        "🕹 <b>Отсутствие лагов и низкий пинг</b>\n"
        "🔄 <b>Доступ к сервисам, недоступным в вашей стране (Netflix, Spotify, Apple)</b>\n"
        "🔒 <b>Отсутствие логирования</b>")


async def main_menu(message):
    await message.answer(text, reply_markup=kb.main, parse_mode="HTML")


async def main_call(message):
    await message.message.edit_text(text, reply_markup=kb.main, parse_mode="HTML")
