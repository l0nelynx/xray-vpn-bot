import logging

from aiogram import F, Router
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
)

import app.database.requests as rq
from .router import is_admin

delete_router = Router()


# ==================== Удаление пользователя ====================

@delete_router.callback_query(F.data.startswith("admin_delete:"))
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


@delete_router.callback_query(F.data.startswith("admin_confirm_delete:"))
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
