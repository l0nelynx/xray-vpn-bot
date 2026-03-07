import logging
import math

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

import app.database.requests as rq
from app.settings import secrets, bot

router = Router()


class AdminState(StatesGroup):
    waiting_message = State()


def is_admin(user_id: int) -> bool:
    return user_id == secrets.get('admin_id')


# ==================== /admin — Главное меню ====================

@router.message(Command("admin"), F.from_user.id == secrets.get('admin_id'))
async def cmd_admin(message: Message):
    total = await rq.get_users_count()
    paid = await rq.get_paid_users_count()
    free = await rq.get_free_users_count()
    by_api = await rq.get_users_count_by_api()

    api_stats = "\n".join(f"  • {api}: {count}" for api, count in by_api.items())

    text = (
        f"<b>Админ-панель</b>\n\n"
        f"Всего пользователей: <b>{total}</b>\n"
        f"Платных: <b>{paid}</b>\n"
        f"Бесплатных: <b>{free}</b>\n\n"
        f"По API провайдерам:\n{api_stats}"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Пользователи", callback_data="admin_users:0")]
    ])

    await message.answer(text, parse_mode='HTML', reply_markup=kb)


# ==================== Возврат в главное меню ====================

@router.callback_query(F.data == "admin_back")
async def admin_back(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await state.clear()

    total = await rq.get_users_count()
    paid = await rq.get_paid_users_count()
    free = await rq.get_free_users_count()
    by_api = await rq.get_users_count_by_api()

    api_stats = "\n".join(f"  • {api}: {count}" for api, count in by_api.items())

    text = (
        f"<b>Админ-панель</b>\n\n"
        f"Всего пользователей: <b>{total}</b>\n"
        f"Платных: <b>{paid}</b>\n"
        f"Бесплатных: <b>{free}</b>\n\n"
        f"По API провайдерам:\n{api_stats}"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Пользователи", callback_data="admin_users:0")]
    ])

    await callback.message.edit_text(text, parse_mode='HTML', reply_markup=kb)


# ==================== Список пользователей (пагинация) ====================

@router.callback_query(F.data.startswith("admin_users:"))
async def admin_users_list(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return

    page = int(callback.data.split(":")[1])
    per_page = 10
    users, total = await rq.get_users_paginated(page, per_page)
    total_pages = max(1, math.ceil(total / per_page))

    buttons = []
    for user in users:
        name = f"@{user.username}" if user.username else f"ID: {user.tg_id}"
        banned = " [BAN]" if user.is_banned else ""
        buttons.append([
            InlineKeyboardButton(
                text=f"{name}{banned}",
                callback_data=f"admin_user:{user.tg_id}"
            )
        ])

    # Навигация
    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton(text="◀ Назад", callback_data=f"admin_users:{page - 1}"))
    nav_row.append(InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data="noop"))
    if page < total_pages - 1:
        nav_row.append(InlineKeyboardButton(text="Вперед ▶", callback_data=f"admin_users:{page + 1}"))
    buttons.append(nav_row)

    buttons.append([InlineKeyboardButton(text="Назад в админку", callback_data="admin_back")])

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

    # Кнопка бана/разбана
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

    # Обновляем карточку
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
    """Вспомогательная функция для обновления карточки пользователя"""
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

    # Получаем информацию перед удалением
    info = await rq.get_user_full_info_by_tg_id(tg_id)

    # Удаляем из RemnaWave API если есть UUID
    if info and info.get("vless_uuid") and info["api_provider"] == "remnawave":
        try:
            from app.api.remnawave.api import delete_user
            await delete_user(info["vless_uuid"])
        except Exception as e:
            logging.error(f"Error deleting user from RemnaWave: {e}")

    # Удаляем из локальной БД
    result = await rq.delete_user_from_db(tg_id)

    if result:
        await callback.answer("Пользователь удален", show_alert=True)
    else:
        await callback.answer("Ошибка при удалении", show_alert=True)

    # Возврат к списку
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
    await state.clear()

    try:
        await bot.send_message(
            chat_id=target_tg_id,
            text=f"Сообщение от администратора:\n\n{message.text}",
            parse_mode='HTML'
        )
        await message.answer(
            f"Сообщение отправлено пользователю <code>{target_tg_id}</code>",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Назад в админку", callback_data="admin_back")]
            ])
        )
    except Exception as e:
        logging.error(f"Error sending message to {target_tg_id}: {e}")
        await message.answer(
            f"Ошибка отправки: {e}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Назад в админку", callback_data="admin_back")]
            ])
        )


# noop для кнопки-счётчика страниц
@router.callback_query(F.data == "noop")
async def noop(callback: CallbackQuery):
    await callback.answer()
