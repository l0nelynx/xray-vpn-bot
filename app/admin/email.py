import logging
import re

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
)

import app.database.requests as rq
from app.settings import secrets
from .router import AdminState, is_admin

email_router = Router()


# ==================== Регистрация email ====================

@email_router.callback_query(F.data.startswith("admin_email:"))
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


@email_router.message(AdminState.email_input, F.from_user.id == secrets.get('admin_id'))
async def admin_email_save(message: Message, state: FSMContext):
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
