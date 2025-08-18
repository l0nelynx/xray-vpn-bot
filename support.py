from aiogram import Bot, Dispatcher
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram import F
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.support.db import init_db
from app.settings import secrets
import logging
import sqlite3
import asyncio

BOT_TOKEN = secrets.get('support_token')
ADMIN_CHAT_ID = secrets.get('admin_id')

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


class SupportStates(StatesGroup):
    WAITING_USER_REPLY = State()
    ADMIN_REPLY = State()


# ======================
# ОБРАБОТЧИКИ ДЛЯ ПОЛЬЗОВАТЕЛЕЙ
# ======================

@dp.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    await message.answer("👋 Здравствуйте! Это служба поддержки CheezyVPN. "
                         "Напишите ваш вопрос, и мы ответим в ближайшее время.")
    await state.set_state(SupportStates.WAITING_USER_REPLY)


@dp.message(SupportStates.WAITING_USER_REPLY)
async def user_message(message: Message, state: FSMContext):
    user_id = message.from_user.id
    username = message.from_user.username
    full_name = message.from_user.full_name

    # Сохраняем пользователя в БД
    conn = sqlite3.connect('support.db')
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO users (user_id, username, full_name) VALUES (?, ?, ?)",
                   (user_id, username, full_name))

    # Сохраняем сообщение
    message_text = message.text or message.caption or "[Медиа-сообщение]"
    cursor.execute("INSERT INTO messages (user_id, message_text) VALUES (?, ?)",
                   (user_id, message_text))
    conn.commit()
    conn.close()

    # Формируем сообщение для администратора
    user_info = f"👤 Пользователь: {full_name} (@{username})"
    user_link = f"<a href='tg://user?id={user_id}'>Написать ответ</a>"

    if message.text:
        text_content = f"✉️ <b>НОВОЕ СООБЩЕНИЕ</b>\n\n{user_info}\nID: {user_id}\n\n{message.text}\n\n{user_link}"
    else:
        text_content = f"✉️ <b>НОВОЕ СООБЩЕНИЕ</b>\n\n{user_info}\nID: {user_id}\n\n[Медиа-сообщение]\n\n{user_link}"

    # Отправляем администратору
    await bot.send_message(
        chat_id=ADMIN_CHAT_ID,
        text=text_content,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Ответить",
                                                                                 callback_data=f"reply_{user_id}")]])
    )

    await message.answer("✅ Ваше сообщение отправлено! Ожидайте ответа.")
    await state.clear()


# ======================
# ОБРАБОТЧИКИ ДЛЯ АДМИНИСТРАТОРА
# ======================

@dp.callback_query(F.data.startswith('reply_'))
async def process_callback_reply(callback: CallbackQuery, state: FSMContext):
    user_id = int(callback.data.split('_')[1])
    await bot.answer_callback_query(callback.id)

    # ПОЛУЧАЕМ ИМЯ ПОЛЬЗОВАТЕЛЯ ИЗ БД
    conn = sqlite3.connect('support.db')
    cursor = conn.cursor()
    cursor.execute("SELECT username FROM users WHERE user_id = ?", (user_id,))
    user_data = cursor.fetchone()
    conn.close()

    username = user_data[0] if user_data else "unknown"

    await state.set_state(SupportStates.ADMIN_REPLY)
    await state.update_data(target_user=user_id)

    await bot.send_message(
        chat_id=ADMIN_CHAT_ID,
        text=f"⬇️ Введите ответ для пользователя @{username}:"
    )


@dp.message(SupportStates.ADMIN_REPLY)
async def admin_reply(message: Message, state: FSMContext):
    data = await state.get_data()
    user_id = data.get('target_user')

    if not user_id:
        await message.reply("Ошибка: пользователь не найден")
        await state.clear()
        return

    try:
        # ПОЛУЧАЕМ ДАННЫЕ ПОЛЬЗОВАТЕЛЯ ИЗ БД
        conn = sqlite3.connect('support.db')
        cursor = conn.cursor()
        cursor.execute("SELECT username, full_name FROM users WHERE user_id = ?", (user_id,))
        user_data = cursor.fetchone()
        conn.close()

        if not user_data:
            await message.reply("❌ Данные пользователя не найдены в БД")
            return

        username = user_data[0]
        full_name = user_data[1]

        # Отправляем ответ пользователю
        if message.text:
            await bot.send_message(
                chat_id=user_id,
                text=f"👨‍💻 <b>Поддержка CheezyVPN:</b>\n\n{message.text}",
                parse_mode="HTML"
            )
            await bot.send_message(
                chat_id=user_id,
                text=f"👨‍💻 <b>Остались еще вопросы? - Используйте /start</b>\n\n",
                parse_mode="HTML"
            )
        # ... остальные типы сообщений

        # Подтверждение администратору (теперь используем данные из БД)
        await message.reply(f"✅ Ответ отправлен пользователю {full_name} (@{username})")

    except Exception as e:
        logger.error(f"Ошибка отправки: {e}")
        await message.reply(f"❌ Ошибка отправки: {e}")

    await state.clear()


if __name__ == '__main__':
    init_db()  # Создаем БД при запуске
    asyncio.run(dp.start_polling(bot))
