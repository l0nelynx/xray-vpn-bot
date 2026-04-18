import logging

from aiogram import F, Router
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
)

import app.database.requests as rq
from app.settings import secrets, bot
from .router import is_admin

migrate_router = Router()


# DISABLED: Marzban migration removed — Remnawave is the only API
# The entire admin_migrate_user handler relied on fetching user from Marzban API
# and creating them in RemnaWave. Since Marzban is no longer used, this is disabled.

@migrate_router.callback_query(F.data.startswith("admin_migrate:"))
async def admin_migrate_user(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    await callback.answer(
        "Миграция из Marzban отключена — все пользователи уже на RemnaWave",
        show_alert=True,
    )
