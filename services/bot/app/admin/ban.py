from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
)

import app.database.requests as rq
from app.settings import secrets
from .router import AdminState, is_admin, BTN_BAN
from .users import _show_user_card

ban_router = Router()


# ==================== Бан / Разбан (из карточки пользователя) ====================

@ban_router.callback_query(F.data.startswith("admin_ban:"))
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


@ban_router.callback_query(F.data.startswith("admin_unban:"))
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


# ==================== Бан/Разбан по ID или username (reply-кнопка) ====================

@ban_router.message(F.text == BTN_BAN, F.from_user.id == secrets.get('admin_id'))
async def admin_ban_input_start(message: Message, state: FSMContext):
    await state.set_state(AdminState.ban_input)
    await message.answer(
        "Введите Telegram ID или @username пользователя для бана/разбана:",
    )


@ban_router.message(AdminState.ban_input, F.from_user.id == secrets.get('admin_id'))
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


@ban_router.callback_query(F.data.startswith("admin_ban_pick:"))
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
