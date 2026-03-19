import math

from aiogram import F, Router
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
)

import app.database.requests as rq
from app.settings import secrets
from .router import is_admin, BTN_PROMOS

promos_router = Router()


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

@promos_router.message(F.text == BTN_PROMOS, F.from_user.id == secrets.get('admin_id'))
async def admin_promos_btn(message: Message):
    text, kb = await _build_promos_list(0)
    await message.answer(text, parse_mode='HTML', reply_markup=kb)


# ==================== Промокоды — пагинация ====================

@promos_router.callback_query(F.data.startswith("admin_promos:"))
async def admin_promos_list(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    page = int(callback.data.split(":")[1])
    text, kb = await _build_promos_list(page)
    await callback.message.edit_text(text, parse_mode='HTML', reply_markup=kb)


# ==================== Карточка промокода ====================

@promos_router.callback_query(F.data.startswith("admin_promo:"))
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
