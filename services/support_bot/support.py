from pathlib import Path
import yaml
from aiogram import Bot, Dispatcher
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.filters import Command, StateFilter
from aiogram import F
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from support_db import init_support_tables, add_support_user, add_support_message, get_support_user
import logging
import asyncio

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ======================
# ЗАГРУЗКА КОНФИГУРАЦИИ
# ======================

def load_config(file_path="config.yml"):
    """Загружает конфигурацию из YAML файла"""
    config_path = Path(file_path)

    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(config_path, 'r') as stream:
        try:
            return yaml.safe_load(stream)
        except yaml.YAMLError as exc:
            raise ValueError(f"Error parsing YAML: {exc}")


# Загрузка конфигурации при импорте модуля
try:
    secrets = load_config()
except Exception as e:
    print(f"⚠️ Error loading secrets: {e}")
    secrets = {}  # Fallback to empty dict


SUPPORT_TOKEN = secrets.get('support_token')
ADMIN_ID = secrets.get('admin_id')
BRAND = secrets.get('branding_name', 'VPN')

bot = Bot(token=SUPPORT_TOKEN)
dp = Dispatcher()


class SupportStates(StatesGroup):
    ADMIN_REPLY = State()


# ======================
# ФИЛЬТРЫ
# ======================

def is_not_admin(message: Message) -> bool:
    """Проверяет что сообщение не от администратора"""
    return message.from_user.id != ADMIN_ID


def is_admin(message: Message) -> bool:
    """Проверяет что сообщение от администратора"""
    return message.from_user.id == ADMIN_ID


# ======================
# ОБРАБОТЧИКИ ДЛЯ ПОЛЬЗОВАТЕЛЕЙ
# ======================

@dp.message(Command("start"))
async def cmd_start(message: Message):
    """Обработчик команды /start"""
    await message.answer(f"👋 Здравствуйте! Это служба поддержки {BRAND}. "
                         "Напишите ваш вопрос или отправьте изображение, и мы ответим в ближайшее время.")


@dp.message(F.text, F.func(is_not_admin))
async def handle_user_text_message(message: Message):
    """Обработчик текстовых сообщений от пользователей (без привязки к состоянию)"""
    user_id = message.from_user.id
    username = message.from_user.username or "unknown"
    full_name = message.from_user.full_name or "Unknown User"

    # Сохраняем пользователя в БД
    add_support_user(user_id, username, full_name)

    # Сохраняем сообщение в БД
    add_support_message(user_id, message.text, is_admin=False)

    # Формируем сообщение для администратора
    user_info = f"👤 <b>Пользователь:</b> {full_name}"
    user_mention = f"@{username}" if username != "unknown" else f"ID: {user_id}"

    text_content = (
        f"✉️ <b>НОВОЕ ТЕКСТОВОЕ СООБЩЕНИЕ</b>\n\n"
        f"{user_info}\n"
        f"<b>Контакт:</b> {user_mention}\n"
        f"<b>ID:</b> {user_id}\n\n"
        f"<b>Сообщение:</b>\n{message.text}"
    )

    # Отправляем администратору с кнопкой ответа
    await bot.send_message(
        chat_id=ADMIN_ID,
        text=text_content,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="Ответить", callback_data=f"reply_{user_id}")
        ]])
    )

    await message.answer("✅ Ваше сообщение отправлено! Ожидайте ответа от поддержки.")


@dp.message(F.photo, F.func(is_not_admin))
async def handle_user_photo_message(message: Message):
    """Обработчик фото от пользователей"""
    user_id = message.from_user.id
    username = message.from_user.username or "unknown"
    full_name = message.from_user.full_name or "Unknown User"

    # Сохраняем пользователя в БД
    add_support_user(user_id, username, full_name)

    # Сохраняем сообщение о фото в БД
    photo_caption = message.caption or "[Фото без описания]"
    add_support_message(user_id, f"[ФОТО] {photo_caption}", is_admin=False)

    # Формируем информацию о пользователе
    user_info = f"👤 <b>Пользователь:</b> {full_name}"
    user_mention = f"@{username}" if username != "unknown" else f"ID: {user_id}"

    caption_text = (
        f"📸 <b>НОВОЕ ФОТО</b>\n\n"
        f"{user_info}\n"
        f"<b>Контакт:</b> {user_mention}\n"
        f"<b>ID:</b> {user_id}\n\n"
    )

    if message.caption:
        caption_text += f"<b>Описание:</b> {message.caption}"

    # Отправляем фото администратору с кнопкой ответа
    await bot.send_photo(
        chat_id=ADMIN_ID,
        photo=message.photo[-1].file_id,  # Берем наибольшее разрешение
        caption=caption_text,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="Ответить", callback_data=f"reply_{user_id}")
        ]])
    )

    await message.answer("✅ Ваше фото отправлено! Ожидайте ответа от поддержки.")


@dp.message(F.document, F.func(is_not_admin))
async def handle_user_document_message(message: Message):
    """Обработчик документов от пользователей"""
    user_id = message.from_user.id
    username = message.from_user.username or "unknown"
    full_name = message.from_user.full_name or "Unknown User"

    # Сохраняем пользователя в БД
    add_support_user(user_id, username, full_name)

    # Сохраняем информацию о документе в БД
    doc_name = message.document.file_name or "document"
    add_support_message(user_id, f"[ДОКУМЕНТ] {doc_name}: {message.caption or ''}", is_admin=False)

    # Формируем информацию о пользователе
    user_info = f"👤 <b>Пользователь:</b> {full_name}"
    user_mention = f"@{username}" if username != "unknown" else f"ID: {user_id}"

    caption_text = (
        f"📄 <b>НОВЫЙ ДОКУМЕНТ</b>\n\n"
        f"{user_info}\n"
        f"<b>Контакт:</b> {user_mention}\n"
        f"<b>ID:</b> {user_id}\n"
        f"<b>Файл:</b> {doc_name}\n\n"
    )

    if message.caption:
        caption_text += f"<b>Описание:</b> {message.caption}"

    # Отправляем документ администратору с кнопкой ответа
    await bot.send_document(
        chat_id=ADMIN_ID,
        document=message.document.file_id,
        caption=caption_text,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="Ответить", callback_data=f"reply_{user_id}")
        ]])
    )

    await message.answer("✅ Ваш документ отправлен! Ожидайте ответа от поддержки.")


@dp.message(F.video, F.func(is_not_admin))
async def handle_user_video_message(message: Message):
    """Обработчик видео от пользователей"""
    user_id = message.from_user.id
    username = message.from_user.username or "unknown"
    full_name = message.from_user.full_name or "Unknown User"

    # Сохраняем пользователя в БД
    add_support_user(user_id, username, full_name)

    # Сохраняем информацию о видео в БД
    add_support_message(user_id, f"[ВИДЕО] {message.caption or '[Видео без описания]'}", is_admin=False)

    # Формируем информацию о пользователе
    user_info = f"👤 <b>Пользователь:</b> {full_name}"
    user_mention = f"@{username}" if username != "unknown" else f"ID: {user_id}"

    caption_text = (
        f"🎥 <b>НОВОЕ ВИДЕО</b>\n\n"
        f"{user_info}\n"
        f"<b>Контакт:</b> {user_mention}\n"
        f"<b>ID:</b> {user_id}\n\n"
    )

    if message.caption:
        caption_text += f"<b>Описание:</b> {message.caption}"

    # Отправляем видео администратору с кнопкой ответа
    await bot.send_video(
        chat_id=ADMIN_ID,
        video=message.video.file_id,
        caption=caption_text,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="Ответить", callback_data=f"reply_{user_id}")
        ]])
    )

    await message.answer("✅ Ваше видео отправлено! Ожидайте ответа от поддержки.")


# ======================
# ОБРАБОТЧИКИ ДЛЯ АДМИНИСТРАТОРА
# ======================

@dp.callback_query(F.data.startswith('reply_'))
async def process_callback_reply(callback: CallbackQuery, state: FSMContext):
    """Обработчик нажатия кнопки 'Ответить'"""
    try:
        user_id = int(callback.data.split('_')[1])
    except (ValueError, IndexError):
        await callback.answer("❌ Ошибка: неверный формат данных", show_alert=True)
        return

    await bot.answer_callback_query(callback.id)

    # ПОЛУЧАЕМ ДАННЫЕ ПОЛЬЗОВАТЕЛЯ ИЗ БД
    user_data = get_support_user(user_id)

    if not user_data:
        await callback.message.reply("❌ Данные пользователя не найдены в БД")
        await state.clear()
        return

    username = user_data[0] if user_data[0] else "unknown"
    full_name = user_data[1] if user_data[1] else "Unknown"

    await state.set_state(SupportStates.ADMIN_REPLY)
    await state.update_data(target_user=user_id, target_username=username, target_full_name=full_name)

    await bot.send_message(
        chat_id=ADMIN_ID,
        text=f"⬇️ <b>Введите ответ для пользователя {full_name} (@{username})</b>\n\n"
             f"Отправьте текст или медиа (фото, документ, видео):",
        parse_mode="HTML"
    )


@dp.message(StateFilter(SupportStates.ADMIN_REPLY), F.text)
async def admin_text_reply(message: Message, state: FSMContext):
    """Обработчик текстового ответа администратора"""
    data = await state.get_data()
    user_id = data.get('target_user')
    full_name = data.get('target_full_name')
    username = data.get('target_username')

    if not user_id:
        await message.reply("❌ Ошибка: пользователь не найден")
        await state.clear()
        return

    try:
        # Отправляем ответ пользователю
        await bot.send_message(
            chat_id=user_id,
            text=f"👨‍💻 <b>Поддержка {BRAND}:</b>\n\n{message.text}",
            parse_mode="HTML"
        )

        # Сохраняем ответ администратора в БД
        add_support_message(user_id, message.text, is_admin=True)

        # Подтверждение администратору
        await message.reply(
            f"✅ <b>Ответ отправлен</b>\n\n"
            f"<b>Пользователь:</b> {full_name} (@{username})\n"
            f"<b>ID:</b> {user_id}",
            parse_mode="HTML"
        )

    except Exception as e:
        logger.error(f"Ошибка отправки ответа: {e}")
        await message.reply(f"❌ Ошибка отправки: {e}")

    await state.clear()


@dp.message(StateFilter(SupportStates.ADMIN_REPLY), F.photo)
async def admin_photo_reply(message: Message, state: FSMContext):
    """Обработчик ответа администратора с фото"""
    data = await state.get_data()
    user_id = data.get('target_user')
    full_name = data.get('target_full_name')
    username = data.get('target_username')

    if not user_id:
        await message.reply("❌ Ошибка: пользователь не найден")
        await state.clear()
        return

    try:
        # Отправляем фото пользователю
        await bot.send_photo(
            chat_id=user_id,
            photo=message.photo[-1].file_id,
            caption=f"👨‍💻 <b>Поддержка {BRAND}:</b>\n\n{message.caption or ''}",
            parse_mode="HTML"
        )

        # Сохраняем ответ администратора в БД
        add_support_message(user_id, f"[ФОТО ОТВЕТ] {message.caption or ''}", is_admin=True)

        # Подтверждение администратору
        await message.reply(
            f"✅ <b>Фото отправлено</b>\n\n"
            f"<b>Пользователь:</b> {full_name} (@{username})\n"
            f"<b>ID:</b> {user_id}",
            parse_mode="HTML"
        )

    except Exception as e:
        logger.error(f"Ошибка отправки фото: {e}")
        await message.reply(f"❌ Ошибка отправки: {e}")

    await state.clear()


@dp.message(StateFilter(SupportStates.ADMIN_REPLY), F.document)
async def admin_document_reply(message: Message, state: FSMContext):
    """Обработчик ответа администратора с документом"""
    data = await state.get_data()
    user_id = data.get('target_user')
    full_name = data.get('target_full_name')
    username = data.get('target_username')

    if not user_id:
        await message.reply("❌ Ошибка: пользователь не найден")
        await state.clear()
        return

    try:
        # Отправляем документ пользователю
        await bot.send_document(
            chat_id=user_id,
            document=message.document.file_id,
            caption=f"👨‍💻 <b>Поддержка {BRAND}:</b>\n\n{message.caption or ''}",
            parse_mode="HTML"
        )

        # Сохраняем ответ администратора в БД
        doc_name = message.document.file_name or "document"
        add_support_message(user_id, f"[ДОКУМЕНТ ОТВЕТ] {doc_name}: {message.caption or ''}", is_admin=True)

        # Подтверждение администратору
        await message.reply(
            f"✅ <b>Документ отправлен</b>\n\n"
            f"<b>Пользователь:</b> {full_name} (@{username})\n"
            f"<b>ID:</b> {user_id}",
            parse_mode="HTML"
        )

    except Exception as e:
        logger.error(f"Ошибка отправки документа: {e}")
        await message.reply(f"❌ Ошибка отправки: {e}")

    await state.clear()


@dp.message(StateFilter(SupportStates.ADMIN_REPLY), F.video)
async def admin_video_reply(message: Message, state: FSMContext):
    """Обработчик ответа администратора с видео"""
    data = await state.get_data()
    user_id = data.get('target_user')
    full_name = data.get('target_full_name')
    username = data.get('target_username')

    if not user_id:
        await message.reply("❌ Ошибка: пользователь не найден")
        await state.clear()
        return

    try:
        # Отправляем видео пользователю
        await bot.send_video(
            chat_id=user_id,
            video=message.video.file_id,
            caption=f"👨‍💻 <b>Поддержка {BRAND}:</b>\n\n{message.caption or ''}",
            parse_mode="HTML"
        )

        # Сохраняем ответ администратора в БД
        add_support_message(user_id, f"[ВИДЕО ОТВЕТ] {message.caption or ''}", is_admin=True)

        # Подтверждение администратору
        await message.reply(
            f"✅ <b>Видео отправлено</b>\n\n"
            f"<b>Пользователь:</b> {full_name} (@{username})\n"
            f"<b>ID:</b> {user_id}",
            parse_mode="HTML"
        )

    except Exception as e:
        logger.error(f"Ошибка отправки видео: {e}")
        await message.reply(f"❌ Ошибка отправки: {e}")

    await state.clear()


if __name__ == '__main__':
    init_support_tables()  # Создаем таблицы поддержки при запуске
    asyncio.run(dp.start_polling(bot))
