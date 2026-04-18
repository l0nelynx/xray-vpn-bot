import logging

from aiogram import F, Router
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
)
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest, TelegramNotFound

import app.database.requests as rq
from app.api.telemt import list_telemt_users, delete_telemt_user
from app.handlers.tools import check_tg_subscription
from app.settings import secrets, bot
from .router import is_admin

logger = logging.getLogger(__name__)

BTN_TELEMT_CLEAN = "Telemt Clean"

telemt_clean_router = Router()

_telemt_clean_cache: dict[int, list[dict]] = {}


@telemt_clean_router.message(F.text == BTN_TELEMT_CLEAN, F.from_user.id == secrets.get('admin_id'))
async def admin_telemt_clean_scan(message: Message):
    """Scan Telemt users: delete those unsubscribed from channel (non-VIP, non-paid)."""
    news_id = secrets.get('news_id')
    if not news_id:
        await message.answer("news_id не настроен в конфигурации.")
        return

    await message.answer(
        "Telemt Clean: получение списка пользователей Telemt...\n"
        "Это может занять некоторое время."
    )

    telemt_users = await list_telemt_users()
    if not telemt_users:
        await message.answer("Пользователей Telemt не найдено.")
        return

    to_delete = []
    checked = 0
    errors = 0
    skipped_vip = 0
    skipped_paid = 0

    for tu in telemt_users:
        username = tu.get("username")
        if not username:
            continue

        try:
            # Find user in bot DB by username
            user_info = await rq.get_full_username_info(username)
            if not user_info:
                # Not in bot DB — skip (could be manually created)
                checked += 1
                continue

            tg_id = user_info["tg_id"]

            # Skip VIP users
            if user_info.get("vip") and user_info["vip"] > 0:
                skipped_vip += 1
                checked += 1
                continue

            # Skip paid users (have transactions)
            has_paid = await rq.user_has_transactions(tg_id)
            if has_paid:
                skipped_paid += 1
                checked += 1
                continue

            # Check channel subscription
            is_subscribed = await check_tg_subscription(
                bot=bot, chat_id=news_id, user_id=tg_id
            )
            if not is_subscribed:
                to_delete.append({
                    "tg_id": tg_id,
                    "username": username,
                })

        except Exception as e:
            logger.error("Telemt Clean scan error for %s: %s", username, e)
            errors += 1

        checked += 1
        if checked % 50 == 0:
            await message.answer(f"Проверено: {checked}/{len(telemt_users)}...")

    if not to_delete:
        await message.answer(
            f"Сканирование завершено.\n"
            f"Проверено: {checked}, VIP: {skipped_vip}, платных: {skipped_paid}, ошибок: {errors}\n"
            f"Неподписанных пользователей для удаления не найдено."
        )
        return

    _telemt_clean_cache[message.from_user.id] = to_delete

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Да, удалить", callback_data="admin_confirm_telemt_clean"),
            InlineKeyboardButton(text="Отмена", callback_data="admin_back"),
        ]
    ])

    await message.answer(
        f"<b>Telemt Clean: результаты сканирования</b>\n\n"
        f"Проверено: {checked}\n"
        f"Пропущено VIP: {skipped_vip}\n"
        f"Пропущено платных: {skipped_paid}\n"
        f"Не подписаны на канал: <b>{len(to_delete)}</b>\n"
        f"Ошибок: {errors}\n\n"
        f"Удалить этих пользователей из Telemt и отправить уведомления?",
        parse_mode='HTML',
        reply_markup=kb,
    )


@telemt_clean_router.callback_query(F.data == "admin_confirm_telemt_clean")
async def admin_confirm_telemt_clean(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return

    to_delete = _telemt_clean_cache.pop(callback.from_user.id, [])
    if not to_delete:
        await callback.answer("Список устарел, запустите сканирование заново.", show_alert=True)
        return

    await callback.message.edit_text("Telemt Clean: выполнение...")

    news_url = secrets.get('news_url', '')
    deleted_count = 0
    notified_count = 0
    error_count = 0

    for user in to_delete:
        tg_id = user["tg_id"]
        username = user["username"]

        try:
            result = await delete_telemt_user(username)
            if result:
                deleted_count += 1
            else:
                error_count += 1
                continue

            # Notify user
            try:
                notification_kb = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="Подписаться на канал", url=news_url)],
                    [InlineKeyboardButton(text="Получить доступ", callback_data="Telemt_Free")],
                ])
                await bot.send_message(
                    chat_id=tg_id,
                    text=(
                        "<b>Доступ к Telemt удалён</b>\n\n"
                        "Вы отписались от нашего канала.\n"
                        "Подпишитесь снова, чтобы получить доступ."
                    ),
                    parse_mode='HTML',
                    reply_markup=notification_kb,
                )
                notified_count += 1
            except (TelegramForbiddenError, TelegramBadRequest, TelegramNotFound):
                pass
            except Exception as e:
                logger.error("Telemt Clean notify error for tg_id=%s: %s", tg_id, e)

        except Exception as e:
            logger.error("Telemt Clean delete error for %s: %s", username, e)
            error_count += 1

    await callback.message.edit_text(
        f"<b>Telemt Clean: завершено</b>\n\n"
        f"Удалено: <b>{deleted_count}</b>\n"
        f"Уведомлено: <b>{notified_count}</b>\n"
        f"Ошибок: <b>{error_count}</b>",
        parse_mode='HTML',
    )
