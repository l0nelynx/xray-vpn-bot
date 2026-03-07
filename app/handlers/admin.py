import logging
import math

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove,
)
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest, TelegramNotFound

import app.database.requests as rq
from app.settings import secrets, bot

router = Router()

# Тексты кнопок главного меню
BTN_USERS = "Пользователи"
BTN_CLEANUP = "Очистка БД"
BTN_FILL_USERNAMES = "Заполнить username"
BTN_BACKUP = "Бекап БД"
BTN_ANNOUNCE = "Объявления"
BTN_CLOSE = "Закрыть админку"


class AdminState(StatesGroup):
    waiting_message = State()
    in_admin = State()
    broadcast_text = State()
    channel_text = State()
    channel_attach_btn = State()


def is_admin(user_id: int) -> bool:
    return user_id == secrets.get('admin_id')


def admin_menu_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN_USERS), KeyboardButton(text=BTN_CLEANUP)],
            [KeyboardButton(text=BTN_FILL_USERNAMES), KeyboardButton(text=BTN_BACKUP)],
            [KeyboardButton(text=BTN_ANNOUNCE)],
            [KeyboardButton(text=BTN_CLOSE)],
        ],
        resize_keyboard=True,
    )


async def _admin_stats_text() -> str:
    total = await rq.get_users_count()
    paid = await rq.get_paid_users_count()
    free = await rq.get_free_users_count()
    by_api = await rq.get_users_count_by_api()

    api_stats = "\n".join(f"  • {api}: {count}" for api, count in by_api.items())

    return (
        f"<b>Админ-панель</b>\n\n"
        f"Всего пользователей: <b>{total}</b>\n"
        f"Платных: <b>{paid}</b>\n"
        f"Бесплатных: <b>{free}</b>\n\n"
        f"По API провайдерам:\n{api_stats}"
    )


# ==================== /admin — Главное меню ====================

@router.message(Command("admin"), F.from_user.id == secrets.get('admin_id'))
async def cmd_admin(message: Message, state: FSMContext):
    await state.set_state(AdminState.in_admin)
    text = await _admin_stats_text()
    await message.answer(text, parse_mode='HTML', reply_markup=admin_menu_kb())


# ==================== Закрыть админку ====================

@router.message(F.text == BTN_CLOSE, F.from_user.id == secrets.get('admin_id'))
async def admin_close(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Админ-панель закрыта.", reply_markup=ReplyKeyboardRemove())


# ==================== Возврат в главное меню (inline) ====================

@router.callback_query(F.data == "admin_back")
async def admin_back(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    # Очищаем FSM (например waiting_message), но остаёмся в админке
    await state.set_state(AdminState.in_admin)

    text = await _admin_stats_text()
    await callback.message.edit_text(text, parse_mode='HTML')


# ==================== Пользователи (reply-кнопка) ====================

@router.message(F.text == BTN_USERS, F.from_user.id == secrets.get('admin_id'))
async def admin_users_btn(message: Message):
    total = await rq.get_users_count()
    per_page = 10
    total_pages = max(1, math.ceil(total / per_page))
    users, _ = await rq.get_users_paginated(0, per_page)

    buttons = []
    for user, is_paid in users:
        name = f"@{user.username}" if user.username else f"ID: {user.tg_id}"
        status = "💲" if is_paid else "🟢"
        banned = " [BAN]" if user.is_banned else ""
        buttons.append([
            InlineKeyboardButton(
                text=f"{status} {name}{banned}",
                callback_data=f"admin_user:{user.tg_id}"
            )
        ])

    nav_row = []
    nav_row.append(InlineKeyboardButton(text=f"1/{total_pages}", callback_data="noop"))
    if total_pages > 1:
        nav_row.append(InlineKeyboardButton(text="Вперед ▶", callback_data="admin_users:1"))
    buttons.append(nav_row)

    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.answer(
        f"<b>Пользователи</b> (стр. 1/{total_pages}, всего: {total})",
        parse_mode='HTML',
        reply_markup=kb
    )


# ==================== Список пользователей (пагинация, inline) ====================

@router.callback_query(F.data.startswith("admin_users:"))
async def admin_users_list(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return

    page = int(callback.data.split(":")[1])
    per_page = 10
    users, total = await rq.get_users_paginated(page, per_page)
    total_pages = max(1, math.ceil(total / per_page))

    buttons = []
    for user, is_paid in users:
        name = f"@{user.username}" if user.username else f"ID: {user.tg_id}"
        status = "💲" if is_paid else "🟢"
        banned = " [BAN]" if user.is_banned else ""
        buttons.append([
            InlineKeyboardButton(
                text=f"{status} {name}{banned}",
                callback_data=f"admin_user:{user.tg_id}"
            )
        ])

    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton(text="◀ Назад", callback_data=f"admin_users:{page - 1}"))
    nav_row.append(InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data="noop"))
    if page < total_pages - 1:
        nav_row.append(InlineKeyboardButton(text="Вперед ▶", callback_data=f"admin_users:{page + 1}"))
    buttons.append(nav_row)

    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    await callback.message.edit_text(
        f"<b>Пользователи</b> (стр. {page + 1}/{total_pages}, всего: {total})",
        parse_mode='HTML',
        reply_markup=kb
    )


# ==================== Карточка пользователя ====================

@router.callback_query(F.data.startswith("admin_user:"))
async def admin_user_card(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return

    tg_id = int(callback.data.split(":")[1])
    info = await rq.get_user_full_info_by_tg_id(tg_id)

    if not info:
        await callback.answer("Пользователь не найден", show_alert=True)
        return

    banned_text = "Да" if info["is_banned"] else "Нет"
    text = (
        f"<b>Карточка пользователя</b>\n\n"
        f"Username: @{info['username'] or '—'}\n"
        f"TG ID: <code>{info['tg_id']}</code>\n"
        f"API: {info['api_provider'] or '—'}\n"
        f"UUID: <code>{info['vless_uuid'] or '—'}</code>\n"
        f"Забанен: {banned_text}"
    )

    if info["is_banned"]:
        ban_btn = InlineKeyboardButton(text="Разбанить", callback_data=f"admin_unban:{tg_id}")
    else:
        ban_btn = InlineKeyboardButton(text="Забанить", callback_data=f"admin_ban:{tg_id}")

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [ban_btn],
        [InlineKeyboardButton(text="Удалить", callback_data=f"admin_delete:{tg_id}")],
        [InlineKeyboardButton(text="Отправить сообщение", callback_data=f"admin_msg:{tg_id}")],
        [InlineKeyboardButton(text="Назад к списку", callback_data="admin_users:0")],
    ])

    await callback.message.edit_text(text, parse_mode='HTML', reply_markup=kb)


# ==================== Бан / Разбан ====================

@router.callback_query(F.data.startswith("admin_ban:"))
async def admin_ban(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return

    tg_id = int(callback.data.split(":")[1])
    result = await rq.ban_user(tg_id)

    if result:
        await callback.answer("Пользователь забанен", show_alert=True)
    else:
        await callback.answer("Пользователь не найден", show_alert=True)
        return

    await _show_user_card(callback, tg_id)


@router.callback_query(F.data.startswith("admin_unban:"))
async def admin_unban(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return

    tg_id = int(callback.data.split(":")[1])
    result = await rq.unban_user(tg_id)

    if result:
        await callback.answer("Пользователь разбанен", show_alert=True)
    else:
        await callback.answer("Пользователь не найден", show_alert=True)
        return

    await _show_user_card(callback, tg_id)


async def _show_user_card(callback: CallbackQuery, tg_id: int):
    info = await rq.get_user_full_info_by_tg_id(tg_id)
    if not info:
        return

    banned_text = "Да" if info["is_banned"] else "Нет"
    text = (
        f"<b>Карточка пользователя</b>\n\n"
        f"Username: @{info['username'] or '—'}\n"
        f"TG ID: <code>{info['tg_id']}</code>\n"
        f"API: {info['api_provider'] or '—'}\n"
        f"UUID: <code>{info['vless_uuid'] or '—'}</code>\n"
        f"Забанен: {banned_text}"
    )

    if info["is_banned"]:
        ban_btn = InlineKeyboardButton(text="Разбанить", callback_data=f"admin_unban:{tg_id}")
    else:
        ban_btn = InlineKeyboardButton(text="Забанить", callback_data=f"admin_ban:{tg_id}")

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [ban_btn],
        [InlineKeyboardButton(text="Удалить", callback_data=f"admin_delete:{tg_id}")],
        [InlineKeyboardButton(text="Отправить сообщение", callback_data=f"admin_msg:{tg_id}")],
        [InlineKeyboardButton(text="Назад к списку", callback_data="admin_users:0")],
    ])

    await callback.message.edit_text(text, parse_mode='HTML', reply_markup=kb)


# ==================== Удаление пользователя ====================

@router.callback_query(F.data.startswith("admin_delete:"))
async def admin_delete_confirm(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return

    tg_id = int(callback.data.split(":")[1])
    info = await rq.get_user_full_info_by_tg_id(tg_id)
    if not info:
        await callback.answer("Пользователь не найден", show_alert=True)
        return

    name = f"@{info['username']}" if info['username'] else str(tg_id)
    text = f"Вы уверены, что хотите удалить пользователя <b>{name}</b>?"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Да, удалить", callback_data=f"admin_confirm_delete:{tg_id}"),
            InlineKeyboardButton(text="Отмена", callback_data=f"admin_user:{tg_id}"),
        ]
    ])

    await callback.message.edit_text(text, parse_mode='HTML', reply_markup=kb)


@router.callback_query(F.data.startswith("admin_confirm_delete:"))
async def admin_confirm_delete(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return

    tg_id = int(callback.data.split(":")[1])

    info = await rq.get_user_full_info_by_tg_id(tg_id)

    if info and info.get("vless_uuid") and info["api_provider"] == "remnawave":
        try:
            from app.api.remnawave.api import delete_user
            await delete_user(info["vless_uuid"])
        except Exception as e:
            logging.error(f"Error deleting user from RemnaWave: {e}")

    result = await rq.delete_user_from_db(tg_id)

    if result:
        await callback.answer("Пользователь удален", show_alert=True)
    else:
        await callback.answer("Ошибка при удалении", show_alert=True)

    await callback.message.edit_text(
        "Пользователь удален.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Назад к списку", callback_data="admin_users:0")]
        ])
    )


# ==================== Отправка сообщения пользователю ====================

@router.callback_query(F.data.startswith("admin_msg:"))
async def admin_msg_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return

    tg_id = int(callback.data.split(":")[1])
    await state.set_state(AdminState.waiting_message)
    await state.update_data(target_tg_id=tg_id)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Отмена", callback_data=f"admin_user:{tg_id}")]
    ])

    await callback.message.edit_text(
        f"Введите текст сообщения для пользователя <code>{tg_id}</code>:",
        parse_mode='HTML',
        reply_markup=kb
    )


@router.message(AdminState.waiting_message, F.from_user.id == secrets.get('admin_id'))
async def admin_msg_send(message: Message, state: FSMContext):
    data = await state.get_data()
    target_tg_id = data.get("target_tg_id")
    await state.set_state(AdminState.in_admin)

    try:
        await bot.send_message(
            chat_id=target_tg_id,
            text=f"Сообщение от администратора:\n\n{message.html_text}",
            parse_mode='HTML'
        )
        await message.answer(
            f"Сообщение отправлено пользователю <code>{target_tg_id}</code>",
            parse_mode='HTML',
        )
    except Exception as e:
        logging.error(f"Error sending message to {target_tg_id}: {e}")
        await message.answer(f"Ошибка отправки: {e}")


# ==================== Очистка БД (reply-кнопка) ====================

@router.message(F.text == BTN_CLEANUP, F.from_user.id == secrets.get('admin_id'))
async def admin_cleanup_scan(message: Message):
    await message.answer(
        "Сканирование пользователей...\nЭто может занять некоторое время.",
    )

    tg_ids = await rq.get_all_user_tg_ids()
    invalid_ids = []

    for tg_id in tg_ids:
        try:
            await bot.get_chat(tg_id)
        except (TelegramForbiddenError, TelegramBadRequest, TelegramNotFound):
            invalid_ids.append(tg_id)
        except Exception:
            pass

    if not invalid_ids:
        await message.answer("Недействительных пользователей не найдено.")
        return

    _cleanup_cache[message.from_user.id] = invalid_ids

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Да, удалить", callback_data="admin_confirm_cleanup"),
            InlineKeyboardButton(text="Отмена", callback_data="admin_back"),
        ]
    ])

    await message.answer(
        f"Найдено недействительных пользователей: <b>{len(invalid_ids)}</b>\n"
        f"(заблокировали бота или удалили аккаунт)\n\n"
        f"Удалить их из базы данных?",
        parse_mode='HTML',
        reply_markup=kb
    )


_cleanup_cache: dict[int, list[int]] = {}


@router.callback_query(F.data == "admin_confirm_cleanup")
async def admin_confirm_cleanup(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return

    invalid_ids = _cleanup_cache.pop(callback.from_user.id, [])
    if not invalid_ids:
        await callback.answer("Список устарел, запустите сканирование заново.", show_alert=True)
        return

    deleted = await rq.delete_users_bulk(invalid_ids)

    await callback.message.edit_text(
        f"Удалено из базы данных: <b>{deleted}</b> пользователей.",
        parse_mode='HTML',
    )


# ==================== Дозаполнение username (reply-кнопка) ====================

@router.message(F.text == BTN_FILL_USERNAMES, F.from_user.id == secrets.get('admin_id'))
async def admin_fill_usernames_scan(message: Message):
    await message.answer("Поиск пользователей без username...")

    tg_ids = await rq.get_users_without_username()

    if not tg_ids:
        await message.answer("Все пользователи уже имеют username.")
        return

    filled = 0
    failed = 0
    for tg_id in tg_ids:
        try:
            chat = await bot.get_chat(tg_id)
            if chat.username:
                await rq.update_username(tg_id, chat.username)
                filled += 1
            else:
                failed += 1
        except Exception:
            failed += 1

    await message.answer(
        f"<b>Дозаполнение username завершено</b>\n\n"
        f"Без username было: <b>{len(tg_ids)}</b>\n"
        f"Заполнено: <b>{filled}</b>\n"
        f"Не удалось (нет username / бот заблокирован): <b>{failed}</b>",
        parse_mode='HTML',
    )


# ==================== Бекап БД (reply-кнопка) ====================

DB_PATH = "db.sqlite3"
MAX_BACKUP_SIZE_MB = 500


@router.message(F.text == BTN_BACKUP, F.from_user.id == secrets.get('admin_id'))
async def admin_backup(message: Message):
    import os
    import zipfile
    from datetime import datetime
    from aiogram.types import FSInputFile

    if not os.path.exists(DB_PATH):
        await message.answer("Файл БД не найден.")
        return

    db_size_mb = os.path.getsize(DB_PATH) / (1024 * 1024)
    if db_size_mb > MAX_BACKUP_SIZE_MB:
        await message.answer(
            f"Размер БД: <b>{db_size_mb:.1f} МБ</b>\n"
            f"Превышает лимит {MAX_BACKUP_SIZE_MB} МБ, отправка невозможна.",
            parse_mode='HTML',
        )
        return

    await message.answer("Создание бекапа...")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    zip_path = f"backup_{timestamp}.zip"

    try:
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            zf.write(DB_PATH, "db.sqlite3")

        zip_size_mb = os.path.getsize(zip_path) / (1024 * 1024)

        await bot.send_document(
            chat_id=message.from_user.id,
            document=FSInputFile(zip_path, filename=f"backup_{timestamp}.zip"),
            caption=(
                f"Бекап БД\n"
                f"Размер БД: {db_size_mb:.1f} МБ\n"
                f"Размер архива: {zip_size_mb:.1f} МБ"
            )
        )
    except Exception as e:
        logging.error(f"Backup error: {e}")
        await message.answer(f"Ошибка создания бекапа: {e}")
    finally:
        if os.path.exists(zip_path):
            os.remove(zip_path)


# ==================== Объявления (reply-кнопка) ====================

@router.message(F.text == BTN_ANNOUNCE, F.from_user.id == secrets.get('admin_id'))
async def admin_announce_menu(message: Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Рассылка всем пользователям", callback_data="announce_broadcast")],
        [InlineKeyboardButton(text="Пост в канал", callback_data="announce_channel")],
    ])
    await message.answer("Выберите тип объявления:", reply_markup=kb)


# --- Рассылка всем пользователям ---

@router.callback_query(F.data == "announce_broadcast")
async def announce_broadcast_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await state.set_state(AdminState.broadcast_text)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Отмена", callback_data="announce_cancel")]
    ])
    await callback.message.edit_text(
        "Введите текст рассылки (HTML-разметка поддерживается):",
        parse_mode='HTML',
        reply_markup=kb,
    )


@router.message(AdminState.broadcast_text, F.from_user.id == secrets.get('admin_id'))
async def announce_broadcast_send(message: Message, state: FSMContext):
    await state.set_state(AdminState.in_admin)
    text = message.html_text

    tg_ids = await rq.get_all_user_tg_ids()
    sent = 0
    failed = 0

    status_msg = await message.answer(f"Рассылка... 0/{len(tg_ids)}")

    for i, tg_id in enumerate(tg_ids):
        try:
            await bot.send_message(chat_id=tg_id, text=text, parse_mode='HTML')
            sent += 1
        except Exception:
            failed += 1
        # Обновляем статус каждые 25 сообщений
        if (i + 1) % 25 == 0:
            try:
                await status_msg.edit_text(f"Рассылка... {i + 1}/{len(tg_ids)}")
            except Exception:
                pass

    await status_msg.edit_text(
        f"<b>Рассылка завершена</b>\n\n"
        f"Всего: <b>{len(tg_ids)}</b>\n"
        f"Доставлено: <b>{sent}</b>\n"
        f"Не доставлено: <b>{failed}</b>",
        parse_mode='HTML',
    )


# --- Пост в канал ---

@router.callback_query(F.data == "announce_channel")
async def announce_channel_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await state.set_state(AdminState.channel_text)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Отмена", callback_data="announce_cancel")]
    ])
    await callback.message.edit_text(
        "Введите текст поста для канала (HTML-разметка поддерживается):",
        parse_mode='HTML',
        reply_markup=kb,
    )


@router.message(AdminState.channel_text, F.from_user.id == secrets.get('admin_id'))
async def announce_channel_ask_button(message: Message, state: FSMContext):
    await state.set_state(AdminState.channel_attach_btn)
    await state.update_data(channel_post_text=message.html_text)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Да, прикрепить", callback_data="announce_ch_btn:yes"),
            InlineKeyboardButton(text="Нет", callback_data="announce_ch_btn:no"),
        ],
        [InlineKeyboardButton(text="Отмена", callback_data="announce_cancel")],
    ])
    await message.answer(
        "Прикрепить кнопку со ссылкой на бота к посту?",
        reply_markup=kb,
    )


@router.callback_query(F.data.startswith("announce_ch_btn:"), AdminState.channel_attach_btn)
async def announce_channel_send(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return

    attach = callback.data.split(":")[1] == "yes"
    data = await state.get_data()
    post_text = data.get("channel_post_text", "")
    await state.set_state(AdminState.in_admin)

    news_id = secrets.get("news_id")
    if not news_id:
        await callback.message.edit_text("news_id не задан в конфигурации.")
        return

    reply_markup = None
    if attach:
        bot_info = await bot.get_me()
        reply_markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Открыть бота", url=f"https://t.me/{bot_info.username}")]
        ])

    try:
        await bot.send_message(
            chat_id=news_id,
            text=post_text,
            parse_mode='HTML',
            reply_markup=reply_markup,
        )
        await callback.message.edit_text("Пост отправлен в канал.")
    except Exception as e:
        logging.error(f"Channel post error: {e}")
        await callback.message.edit_text(f"Ошибка отправки в канал: {e}")


# --- Отмена объявления ---

@router.callback_query(F.data == "announce_cancel")
async def announce_cancel(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await state.set_state(AdminState.in_admin)
    await callback.message.edit_text("Отменено.")


# noop для кнопки-счётчика страниц
@router.callback_query(F.data == "noop")
async def noop(callback: CallbackQuery):
    await callback.answer()
