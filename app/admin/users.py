import math

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
)

import app.database.requests as rq
from app.settings import secrets
from .router import AdminState, is_admin, BTN_USERS

users_router = Router()

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

@users_router.message(F.text == BTN_USERS, F.from_user.id == secrets.get('admin_id'))
async def admin_users_btn(message: Message):
    text, kb = await _build_users_list(0, "id", "")
    await message.answer(text, parse_mode='HTML', reply_markup=kb)


# ==================== Список пользователей (пагинация, inline) ====================

@users_router.callback_query(F.data.startswith("admin_users:"))
async def admin_users_list(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return

    page, sort, search = _parse_cb(callback.data)
    text, kb = await _build_users_list(page, sort, search)
    await callback.message.edit_text(text, parse_mode='HTML', reply_markup=kb)


# ==================== Поиск пользователей ====================

@users_router.callback_query(F.data == "admin_user_search")
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


@users_router.message(AdminState.user_search, F.from_user.id == secrets.get('admin_id'))
async def admin_user_search_result(message: Message, state: FSMContext):
    await state.set_state(AdminState.in_admin)
    query = message.text.strip().lstrip("@")
    text, kb = await _build_users_list(0, "id", query)
    await message.answer(text, parse_mode='HTML', reply_markup=kb)


# ==================== Карточка пользователя ====================

async def _build_user_card(tg_id: int) -> tuple[str, InlineKeyboardMarkup] | None:
    """Формирует текст карточки пользователя и клавиатуру."""
    info = await rq.get_user_full_info_by_tg_id(tg_id)
    if not info:
        return None

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

    # Блок транзакций
    transactions = await rq.get_user_transactions_detailed(tg_id)
    if transactions:
        text += "\n\n<b>Транзакции:</b>\n"
        status_icons = {
            ("confirmed", 1): "✅",
            ("confirmed", 0): "📦",
            ("pending", None): "⏳",
            ("pending", 0): "⏳",
            ("pending", 1): "⏳",
            ("created", None): "🔄",
            ("created", 0): "🔄",
        }
        for tx in transactions[:5]:
            icon = status_icons.get(
                (tx["order_status"], tx["delivery_status"]),
                "❓"
            )
            created = (tx["created_at"] or "—")[:16]
            method = tx["payment_method"] or "—"
            amount = tx["amount"] if tx["amount"] is not None else "—"
            days_tx = tx["days_ordered"] or "—"
            text += f"{icon} {created} | {method} | {amount} | {days_tx}д\n"
        if len(transactions) > 5:
            text += f"... и ещё {len(transactions) - 5}\n"
    else:
        text += "\n\n<b>Транзакции:</b> нет"

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

    return text, InlineKeyboardMarkup(inline_keyboard=rows)


@users_router.callback_query(F.data.startswith("admin_user:"))
async def admin_user_card(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return

    tg_id = int(callback.data.split(":")[1])
    result = await _build_user_card(tg_id)

    if not result:
        await callback.answer("Пользователь не найден", show_alert=True)
        return

    text, kb = result
    await callback.message.edit_text(text, parse_mode='HTML', reply_markup=kb)


async def _show_user_card(callback: CallbackQuery, tg_id: int):
    result = await _build_user_card(tg_id)
    if not result:
        return
    text, kb = result
    await callback.message.edit_text(text, parse_mode='HTML', reply_markup=kb)
