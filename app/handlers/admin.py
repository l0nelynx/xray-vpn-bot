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
BTN_PROMOS = "Промокоды"
BTN_BAN = "Бан/Разбан"
BTN_LOGS = "Логи ошибок"
BTN_CLOSE = "Закрыть админку"


class AdminState(StatesGroup):
    waiting_message = State()
    in_admin = State()
    broadcast_text = State()
    channel_text = State()
    channel_attach_btn = State()
    user_search = State()
    email_input = State()
    ban_input = State()


def is_admin(user_id: int) -> bool:
    return user_id == secrets.get('admin_id')


def admin_menu_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN_USERS), KeyboardButton(text=BTN_CLEANUP)],
            [KeyboardButton(text=BTN_FILL_USERNAMES), KeyboardButton(text=BTN_BACKUP)],
            [KeyboardButton(text=BTN_PROMOS), KeyboardButton(text=BTN_ANNOUNCE)],
            [KeyboardButton(text=BTN_BAN), KeyboardButton(text=BTN_LOGS)],
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


# ==================== Пользователи — helpers ====================

# Формат callback: admin_users:{page}:{sort}:{search}
# sort: id, alpha, paid, free
# search: строка поиска (пустая = все)

SORT_LABELS = {"id": "По ID", "alpha": "По алфавиту", "paid": "Платные", "free": "Бесплатные"}


def _make_cb(page: int, sort: str, search: str) -> str:
    return f"admin_users:{page}:{sort}:{search}"


def _parse_cb(data: str):
    parts = data.split(":", 3)
    page = int(parts[1]) if len(parts) > 1 else 0
    sort = parts[2] if len(parts) > 2 else "id"
    search = parts[3] if len(parts) > 3 else ""
    return page, sort, search


async def _build_users_list(page: int, sort: str, search: str):
    per_page = 10
    users, total = await rq.get_users_paginated(page, per_page, sort=sort, search=search)
    total_pages = max(1, math.ceil(total / per_page))

    buttons = []
    for user, is_paid in users:
        name = f"@{user.username} ({user.tg_id})" if user.username else f"ID: {user.tg_id}"
        status = "💲" if is_paid else "🟢"
        banned = " [BAN]" if user.is_banned else ""
        buttons.append([
            InlineKeyboardButton(
                text=f"{status} {name}{banned}",
                callback_data=f"admin_user:{user.tg_id}"
            )
        ])

    # Навигация
    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton(text="◀", callback_data=_make_cb(page - 1, sort, search)))
    nav_row.append(InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data="noop"))
    if page < total_pages - 1:
        nav_row.append(InlineKeyboardButton(text="▶", callback_data=_make_cb(page + 1, sort, search)))
    buttons.append(nav_row)

    # Кнопки сортировки
    sort_row = []
    for key, label in SORT_LABELS.items():
        marker = "• " if key == sort else ""
        sort_row.append(InlineKeyboardButton(
            text=f"{marker}{label}",
            callback_data=_make_cb(0, key, search)
        ))
    buttons.append(sort_row[:2])
    buttons.append(sort_row[2:])

    # Кнопка поиска и сброса
    search_row = [InlineKeyboardButton(text="Поиск", callback_data="admin_user_search")]
    if search:
        search_row.append(InlineKeyboardButton(text="Сбросить поиск", callback_data=_make_cb(0, sort, "")))
    buttons.append(search_row)

    search_hint = f"\nПоиск: <b>{search}</b>" if search else ""
    sort_hint = SORT_LABELS.get(sort, "")
    text = (
        f"<b>Пользователи</b> (стр. {page + 1}/{total_pages}, всего: {total})\n"
        f"Сортировка: {sort_hint}{search_hint}"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    return text, kb


# ==================== Пользователи (reply-кнопка) ====================

@router.message(F.text == BTN_USERS, F.from_user.id == secrets.get('admin_id'))
async def admin_users_btn(message: Message):
    text, kb = await _build_users_list(0, "id", "")
    await message.answer(text, parse_mode='HTML', reply_markup=kb)


# ==================== Список пользователей (пагинация, inline) ====================

@router.callback_query(F.data.startswith("admin_users:"))
async def admin_users_list(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return

    page, sort, search = _parse_cb(callback.data)
    text, kb = await _build_users_list(page, sort, search)
    await callback.message.edit_text(text, parse_mode='HTML', reply_markup=kb)


# ==================== Поиск пользователей ====================

@router.callback_query(F.data == "admin_user_search")
async def admin_user_search_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await state.set_state(AdminState.user_search)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Отмена", callback_data=_make_cb(0, "id", ""))]
    ])
    await callback.message.edit_text(
        "Введите фрагмент username или Telegram ID для поиска:",
        reply_markup=kb,
    )


@router.message(AdminState.user_search, F.from_user.id == secrets.get('admin_id'))
async def admin_user_search_result(message: Message, state: FSMContext):
    await state.set_state(AdminState.in_admin)
    query = message.text.strip().lstrip("@")
    text, kb = await _build_users_list(0, "id", query)
    await message.answer(text, parse_mode='HTML', reply_markup=kb)


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
    email_text = info.get("email") or "—"
    text = (
        f"<b>Карточка пользователя</b>\n\n"
        f"Username: @{info['username'] or '—'}\n"
        f"TG ID: <code>{info['tg_id']}</code>\n"
        f"Email: {email_text}\n"
        f"API: {info['api_provider'] or '—'}\n"
        f"UUID: <code>{info['vless_uuid'] or '—'}</code>\n"
        f"Забанен: {banned_text}"
    )

    if info["is_banned"]:
        ban_btn = InlineKeyboardButton(text="Разбанить", callback_data=f"admin_unban:{tg_id}")
    else:
        ban_btn = InlineKeyboardButton(text="Забанить", callback_data=f"admin_ban:{tg_id}")

    rows = [
        [ban_btn],
        [InlineKeyboardButton(text="Удалить", callback_data=f"admin_delete:{tg_id}")],
        [InlineKeyboardButton(text="Отправить сообщение", callback_data=f"admin_msg:{tg_id}")],
        [InlineKeyboardButton(text="Регистрация email", callback_data=f"admin_email:{tg_id}")],
    ]
    if info["api_provider"] != "remnawave":
        rows.append([InlineKeyboardButton(text="Миграция в RemnaWave", callback_data=f"admin_migrate:{tg_id}")])
    rows.append([InlineKeyboardButton(text="Назад к списку", callback_data="admin_users:0")])

    kb = InlineKeyboardMarkup(inline_keyboard=rows)

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
    email_text = info.get("email") or "—"
    text = (
        f"<b>Карточка пользователя</b>\n\n"
        f"Username: @{info['username'] or '—'}\n"
        f"TG ID: <code>{info['tg_id']}</code>\n"
        f"Email: {email_text}\n"
        f"API: {info['api_provider'] or '—'}\n"
        f"UUID: <code>{info['vless_uuid'] or '—'}</code>\n"
        f"Забанен: {banned_text}"
    )

    if info["is_banned"]:
        ban_btn = InlineKeyboardButton(text="Разбанить", callback_data=f"admin_unban:{tg_id}")
    else:
        ban_btn = InlineKeyboardButton(text="Забанить", callback_data=f"admin_ban:{tg_id}")

    rows = [
        [ban_btn],
        [InlineKeyboardButton(text="Удалить", callback_data=f"admin_delete:{tg_id}")],
        [InlineKeyboardButton(text="Отправить сообщение", callback_data=f"admin_msg:{tg_id}")],
        [InlineKeyboardButton(text="Регистрация email", callback_data=f"admin_email:{tg_id}")],
    ]
    if info["api_provider"] != "remnawave":
        rows.append([InlineKeyboardButton(text="Миграция в RemnaWave", callback_data=f"admin_migrate:{tg_id}")])
    rows.append([InlineKeyboardButton(text="Назад к списку", callback_data="admin_users:0")])

    kb = InlineKeyboardMarkup(inline_keyboard=rows)

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


# ==================== Миграция пользователя в RemnaWave ====================

@router.callback_query(F.data.startswith("admin_migrate:"))
async def admin_migrate_user(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return

    tg_id = int(callback.data.split(":")[1])
    info = await rq.get_user_full_info_by_tg_id(tg_id)

    if not info:
        await callback.answer("Пользователь не найден", show_alert=True)
        return

    if info["api_provider"] == "remnawave":
        await callback.answer("Пользователь уже на RemnaWave", show_alert=True)
        return

    username = info["username"]
    if not username:
        await callback.answer("У пользователя нет username, миграция невозможна", show_alert=True)
        return

    await callback.message.edit_text(
        f"Миграция @{username} в RemnaWave...",
        parse_mode='HTML',
    )

    from app.handlers.tools import detect_user_api_provider, get_user_info, add_new_user_info, get_user_days

    try:
        user_info = await get_user_info(username, api="marzban")

        if user_info == 404:
            await callback.message.edit_text(
                f"Пользователь @{username} не найден в Marzban.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="Назад к карточке", callback_data=f"admin_user:{tg_id}")]
                ])
            )
            return

        expire_days = await get_user_days(user_info)
        data_limit = user_info.get("data_limit", 0)
        is_pro = user_info.get("status") == "active" and data_limit is None

        if is_pro:
            squad_id = secrets.get("rw_pro_id")
            external_squad_id = secrets.get("rw_ext_pro_id")
            description = "Migrated from Marzban (Pro) by admin"
        else:
            squad_id = secrets.get("rw_free_id")
            external_squad_id = secrets.get("rw_ext_free_id")
            description = "Migrated from Marzban (Free) by admin"

        if data_limit == 0 or data_limit is None:
            data_limit = 0
        else:
            data_limit = data_limit // (1024 * 1024 * 1024)

        new_user_info = await add_new_user_info(
            name=username,
            userid=tg_id,
            limit=data_limit,
            res_strat="month",
            expire_days=expire_days,
            api="remnawave",
            email=f"{username}@marzban.ru",
            description=description,
            squad_id=squad_id,
            external_squad_id=external_squad_id
        )

        if not new_user_info:
            await callback.message.edit_text(
                f"Ошибка создания пользователя в RemnaWave.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="Назад к карточке", callback_data=f"admin_user:{tg_id}")]
                ])
            )
            return

        # Обновляем БД
        await rq.update_user_api_info(
            tg_id=tg_id,
            username=username,
            vless_uuid=new_user_info.get("uuid"),
            api_provider="remnawave",
        )

        subscription_url = new_user_info.get("subscription_url")

        # Отправляем пользователю сообщение об обновлении подписки
        try:
            import app.keyboards as kb_module
            await bot.send_message(
                chat_id=tg_id,
                text=(
                    f"Ваша подписка была обновлена!\n\n"
                    f"Больше стабильности, больше скорости, больше фичей 🚀\n\n"
                    f"Ссылка для подключения: {subscription_url}"
                ),
                parse_mode='HTML',
                reply_markup=kb_module.connect(subscription_url),
            )
        except Exception as e:
            logging.error(f"Failed to notify user {tg_id} about migration: {e}")

        # Уведомляем админа об успехе
        from app.locale.lang_ru import admin_migration_message
        await callback.message.edit_text(
            admin_migration_message.format(
                username=username,
                user_id=tg_id,
                expire_days=expire_days,
                data_limit=data_limit if data_limit > 0 else 'Без лимита',
                sub_type='Pro' if is_pro else 'Free'
            ),
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Назад к карточке", callback_data=f"admin_user:{tg_id}")]
            ])
        )

    except Exception as e:
        logging.error(f"Admin migration error for {username}: {e}")
        await callback.message.edit_text(
            f"Ошибка миграции @{username}:\n<code>{e}</code>",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Назад к карточке", callback_data=f"admin_user:{tg_id}")]
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


# ==================== Регистрация email ====================

@router.callback_query(F.data.startswith("admin_email:"))
async def admin_email_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return

    tg_id = int(callback.data.split(":")[1])
    await state.set_state(AdminState.email_input)
    await state.update_data(email_tg_id=tg_id)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Отмена", callback_data=f"admin_user:{tg_id}")]
    ])

    await callback.message.edit_text(
        f"Введите email для пользователя <code>{tg_id}</code>:",
        parse_mode='HTML',
        reply_markup=kb,
    )


@router.message(AdminState.email_input, F.from_user.id == secrets.get('admin_id'))
async def admin_email_save(message: Message, state: FSMContext):
    import re
    data = await state.get_data()
    tg_id = data.get("email_tg_id")
    await state.set_state(AdminState.in_admin)

    email = message.text.strip()

    # Валидация email
    if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
        await message.answer(
            f"Некорректный email: <code>{email}</code>\nПопробуйте снова через карточку пользователя.",
            parse_mode='HTML',
        )
        return

    result = await rq.update_user_email(tg_id, email)
    if not result:
        await message.answer("Пользователь не найден в БД.")
        return

    await message.answer(
        f"Email <code>{email}</code> сохранён для пользователя <code>{tg_id}</code>.",
        parse_mode='HTML',
    )

    # Пробуем найти пользователя по email в RemnaWave и обновить vless_uuid
    info = await rq.get_user_full_info_by_tg_id(tg_id)
    if info:
        try:
            from app.api.remnawave.api import get_user_from_email
            rw_user = await get_user_from_email(email)
            if rw_user and rw_user.get("uuid"):
                await rq.update_user_api_info(
                    tg_id=tg_id,
                    username=info.get("username"),
                    vless_uuid=rw_user["uuid"],
                    api_provider="remnawave",
                )
                await message.answer(
                    f"Пользователь найден в RemnaWave по email.\n"
                    f"UUID: <code>{rw_user['uuid']}</code>\n"
                    f"API провайдер обновлён на remnawave.",
                    parse_mode='HTML',
                )
        except Exception as e:
            logging.error(f"Error looking up user by email {email}: {e}")


# ==================== Бан/Разбан по ID или username (reply-кнопка) ====================

@router.message(F.text == BTN_BAN, F.from_user.id == secrets.get('admin_id'))
async def admin_ban_input_start(message: Message, state: FSMContext):
    await state.set_state(AdminState.ban_input)
    await message.answer(
        "Введите Telegram ID или @username пользователя для бана/разбана:",
    )


@router.message(AdminState.ban_input, F.from_user.id == secrets.get('admin_id'))
async def admin_ban_input_process(message: Message, state: FSMContext):
    await state.set_state(AdminState.in_admin)
    text = message.text.strip().lstrip("@")

    if text.isdigit():
        tg_id = int(text)
        await _toggle_ban_and_respond(message, tg_id)
        return

    # Поиск по username
    users = await rq.get_all_users_by_username(text)

    if not users:
        await message.answer(f"Пользователь с username <b>{text}</b> не найден.", parse_mode='HTML')
        return

    if len(users) == 1:
        await _toggle_ban_and_respond(message, users[0]["tg_id"])
        return

    # Несколько совпадений — disambiguation
    buttons = []
    for u in users:
        banned = " [BAN]" if u["is_banned"] else ""
        buttons.append([
            InlineKeyboardButton(
                text=f"@{u['username']} ({u['tg_id']}){banned}",
                callback_data=f"admin_ban_pick:{u['tg_id']}"
            )
        ])
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.answer(
        f"Найдено несколько пользователей с username <b>{text}</b>.\nВыберите:",
        parse_mode='HTML',
        reply_markup=kb,
    )


@router.callback_query(F.data.startswith("admin_ban_pick:"))
async def admin_ban_pick(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    tg_id = int(callback.data.split(":")[1])
    await _toggle_ban_and_respond(callback.message, tg_id)
    await callback.answer()


async def _toggle_ban_and_respond(message: Message, tg_id: int):
    info = await rq.get_user_full_info_by_tg_id(tg_id)
    if not info:
        await message.answer(f"Пользователь с ID <code>{tg_id}</code> не найден.", parse_mode='HTML')
        return

    if info["is_banned"]:
        await rq.unban_user(tg_id)
        action = "разбанен"
    else:
        await rq.ban_user(tg_id)
        action = "забанен"

    name = f"@{info['username']}" if info.get("username") else str(tg_id)
    await message.answer(
        f"Пользователь {name} (<code>{tg_id}</code>) <b>{action}</b>.",
        parse_mode='HTML',
    )


# ==================== Логи ошибок (reply-кнопка) ====================

@router.message(F.text == BTN_LOGS, F.from_user.id == secrets.get('admin_id'))
async def admin_error_logs(message: Message):
    from app.log_buffer import error_log_handler

    if not error_log_handler or not error_log_handler.get_entries():
        await message.answer("Логи ошибок пусты.")
        return

    full_text = error_log_handler.format_entries_for_display()

    if len(full_text) <= 4096:
        await message.answer(full_text, parse_mode='HTML')
        return

    # Слишком длинный текст — отправляем по одной записи
    for entry in error_log_handler.get_entries():
        ts = entry.timestamp.strftime("%Y-%m-%d %H:%M:%S")
        msg = entry.message[:500] if len(entry.message) > 500 else entry.message
        text = f"<b>[{entry.level}]</b> {ts}\n<b>{entry.logger_name}</b>\n<code>{msg}</code>"
        if entry.traceback:
            tr = entry.traceback[:300] if len(entry.traceback) > 300 else entry.traceback
            text += f"\n<pre>{tr}</pre>"
        if len(text) > 4096:
            text = text[:4093] + "..."
        await message.answer(text, parse_mode='HTML')


# ==================== Промокоды — helpers ====================

async def _build_promos_list(page: int):
    per_page = 10
    promos, total = await rq.get_promos_paginated(page, per_page)
    total_pages = max(1, math.ceil(total / per_page))

    buttons = []
    for p in promos:
        owner = f"@{p['owner_username']}" if p['owner_username'] else str(p['owner_tg_id'])
        buttons.append([
            InlineKeyboardButton(
                text=f"{p['promo_code']} ({owner}) [{p['usage_count']} исп.]",
                callback_data=f"admin_promo:{p['promo_code']}"
            )
        ])

    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton(text="◀", callback_data=f"admin_promos:{page - 1}"))
    nav_row.append(InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data="noop"))
    if page < total_pages - 1:
        nav_row.append(InlineKeyboardButton(text="▶", callback_data=f"admin_promos:{page + 1}"))
    buttons.append(nav_row)

    text = f"<b>Промокоды</b> (стр. {page + 1}/{total_pages}, всего: {total})"
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    return text, kb


# ==================== Промокоды (reply-кнопка) ====================

@router.message(F.text == BTN_PROMOS, F.from_user.id == secrets.get('admin_id'))
async def admin_promos_btn(message: Message):
    text, kb = await _build_promos_list(0)
    await message.answer(text, parse_mode='HTML', reply_markup=kb)


# ==================== Промокоды — пагинация ====================

@router.callback_query(F.data.startswith("admin_promos:"))
async def admin_promos_list(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    page = int(callback.data.split(":")[1])
    text, kb = await _build_promos_list(page)
    await callback.message.edit_text(text, parse_mode='HTML', reply_markup=kb)


# ==================== Карточка промокода ====================

@router.callback_query(F.data.startswith("admin_promo:"))
async def admin_promo_card(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return

    promo_code = callback.data.split(":", 1)[1]
    promo = await rq.get_promo_by_code(promo_code)

    if not promo:
        await callback.answer("Промокод не найден", show_alert=True)
        return

    # Получаем username владельца
    owner_info = await rq.get_user_full_info_by_tg_id(promo["tg_id"])
    owner_name = f"@{owner_info['username']}" if owner_info and owner_info.get("username") else "—"

    # Список приглашённых
    usage_users = await rq.get_promo_usage_users(promo_code)

    invited_lines = ""
    if usage_users:
        lines = []
        for u in usage_users:
            name = f"@{u['username']}" if u['username'] else str(u['tg_id'])
            lines.append(f"  • {name}")
        invited_lines = "\n".join(lines)

    text = (
        f"<b>Промокод:</b> <code>{promo['promo_code']}</code>\n"
        f"<b>Владелец:</b> {owner_name} (<code>{promo['tg_id']}</code>)\n"
        f"<b>Куплено по промокоду:</b> {promo['days_purchased']} дней\n"
        f"<b>Начислено бонусов:</b> {promo['days_rewarded']} дней\n\n"
        f"<b>Приглашённые пользователи ({len(usage_users)}):</b>\n"
        f"{invited_lines if invited_lines else '  нет'}"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Назад к списку", callback_data="admin_promos:0")]
    ])

    await callback.message.edit_text(text, parse_mode='HTML', reply_markup=kb)


# noop для кнопки-счётчика страниц
@router.callback_query(F.data == "noop")
async def noop(callback: CallbackQuery):
    await callback.answer()
