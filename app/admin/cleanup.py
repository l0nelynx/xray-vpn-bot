from aiogram import F, Router
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
)
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest, TelegramNotFound

import app.database.requests as rq
from app.settings import secrets, bot
from .router import is_admin, BTN_CLEANUP, BTN_FILL_USERNAMES

cleanup_router = Router()

_cleanup_cache: dict[int, list[int]] = {}


# ==================== Очистка БД (reply-кнопка) ====================

@cleanup_router.message(F.text == BTN_CLEANUP, F.from_user.id == secrets.get('admin_id'))
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


@cleanup_router.callback_query(F.data == "admin_confirm_cleanup")
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

@cleanup_router.message(F.text == BTN_FILL_USERNAMES, F.from_user.id == secrets.get('admin_id'))
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
