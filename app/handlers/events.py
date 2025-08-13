import os

from app.settings import bot, secrets
from app.views import start_bot_msg, stop_bot_msg
from app.database.models import async_main
import app.keyboards as kb
import app.database.requests as rq


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


crypto = secrets.get('crypto')

text_base = ("<b>🔓 *Добро пожаловать в CheezyVPN!* 🔓</b>\n\n"
             "🚀 <b>Забудь о региональных блокировках 🚫 и медленном интернете 🐢!"
             "CheezyVPN – твой билет в свободный интернет без границ:</b>\n"
             "⚡️ <b>Молниеносная скорость:</b>Стримы в 4K, игры без лагов – всё летает! \n"
             "🔒 <b>Макс. безопасность:</b>Военная шифровка защитит твои данные от посторонних глаз.\n"
             "📱 <b>Простота:</b>Подключайся в 1 клик! Никакой сложной настройки.\n"
             "🤫 <b>Без логов:</b>Мы НЕ храним твою историю. Полная анонимность гарантирована!\n")
text_new = "⚡️<b>Ты еще не с нами? - скорее подключайся</b>\n"
text_free = ("📱<b>У тебя активная бесплатная подписка,</b>\n"
             "<b>НО!</b> Хочешь *по-настоящему* сорвать все ограничения? 😉\n"
             "👉 <b>БЕЗЛИМИТНЫЙ трафик</b> для стримов, игр, скачиваний?\n"
             "👉 <b>МАКСИМАЛЬНУЮ скорость</b> без тормозов?\n"
             "✨ Тогда платные тарифы <b>Сырный</b> и <b>Сырный ПРО</b>(скоро будет доступен)"
             " – твой пропуск в мир безграничных возможностей! За копейки в день!\n"
             "🔓 Не ограничивай себя пробником – <b>выбери полную свободу!</b> Посмотри платные тарифы →\n")
text_pro = ("⚡️<b>Вау, круто - ты уже с нами!</b>\n"
            "Ниже можешь посмотреть информацию о текущей подписке, а также продлить её")


async def main_menu(message, menu_type):
    if menu_type == "pro":
        await message(text_pro, reply_markup=kb.main_pro, parse_mode="HTML")
    elif menu_type == "free":
        await message(text_free, reply_markup=kb.main_free, parse_mode="HTML")
    else:
        await message(text_base+text_new, reply_markup=kb.main_new, parse_mode="HTML")


async def main_call(message, menu_type):
    await main_menu(message, menu_type)
