import logging

from aiogram import F, Router
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
)
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest, TelegramNotFound

import app.database.requests as rq
import app.api.remnawave.api as rem
from app.handlers.tools import check_tg_subscription
from app.settings import secrets, bot
from .router import is_admin, BTN_SUB_CLEAN

logger = logging.getLogger(__name__)

sub_clean_router = Router()

# Cache: admin_id -> list of dicts with user info to disable
_sub_clean_cache: dict[int, list[dict]] = {}


@sub_clean_router.message(F.text == BTN_SUB_CLEAN, F.from_user.id == secrets.get('admin_id'))
async def admin_sub_clean_scan(message: Message):
    """Scan free non-VIP RemnaWave users for channel subscription."""
    news_id = secrets.get('news_id')
    if not news_id:
        await message.answer("news_id не настроен в конфигурации.")
        return

    await message.answer(
        "Sub Clean: сканирование бесплатных пользователей...\n"
        "Это может занять некоторое время."
    )

    free_users = await rq.get_free_non_vip_remnawave_users()
    if not free_users:
        await message.answer("Бесплатных пользователей без VIP не найдено.")
        return

    to_disable = []
    checked = 0
    errors = 0

    for user in free_users:
        try:
            is_subscribed = await check_tg_subscription(
                bot=bot, chat_id=news_id, user_id=user["tg_id"]
            )
            if not is_subscribed:
                # Get current status from RemnaWave
                rw_user = None
                if user.get("username"):
                    rw_user = await rem.get_user_from_username(user["username"])
                if rw_user and rw_user.get("status") != "disabled":
                    to_disable.append({
                        "tg_id": user["tg_id"],
                        "username": user["username"],
                        "vless_uuid": user["vless_uuid"],
                        "current_status": rw_user["status"],
                    })
        except Exception as e:
            logger.error("Sub Clean scan error for tg_id=%s: %s", user["tg_id"], e)
            errors += 1

        checked += 1
        if checked % 50 == 0:
            await message.answer(f"Проверено: {checked}/{len(free_users)}...")

    if not to_disable:
        await message.answer(
            f"Сканирование завершено.\n"
            f"Проверено: {checked}, ошибок: {errors}\n"
            f"Неподписанных пользователей для отключения не найдено."
        )
        return

    _sub_clean_cache[message.from_user.id] = to_disable

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Да, отключить", callback_data="admin_confirm_sub_clean"),
            InlineKeyboardButton(text="Отмена", callback_data="admin_back"),
        ]
    ])

    await message.answer(
        f"<b>Sub Clean: результаты сканирования</b>\n\n"
        f"Проверено: {checked}\n"
        f"Не подписаны на канал: <b>{len(to_disable)}</b>\n"
        f"Ошибок: {errors}\n\n"
        f"Отключить этих пользователей в RemnaWave и отправить уведомления?",
        parse_mode='HTML',
        reply_markup=kb,
    )


@sub_clean_router.callback_query(F.data == "admin_confirm_sub_clean")
async def admin_confirm_sub_clean(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return

    to_disable = _sub_clean_cache.pop(callback.from_user.id, [])
    if not to_disable:
        await callback.answer("Список устарел, запустите сканирование заново.", show_alert=True)
        return

    await callback.message.edit_text("Sub Clean: выполнение...")

    news_url = secrets.get('news_url', '')
    disabled_count = 0
    notified_count = 0
    error_count = 0

    for user in to_disable:
        tg_id = user["tg_id"]
        vless_uuid = user["vless_uuid"]
        current_status = user["current_status"]

        try:
            # Save original status before disabling
            await rq.create_disabled_user(tg_id, current_status)

            # Disable in RemnaWave
            result = await rem.update_user(vless_uuid, status="disabled")
            if result:
                disabled_count += 1
            else:
                error_count += 1
                continue

            # Send notification to user
            try:
                notification_kb = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="Подписаться на канал", url=news_url)],
                    [InlineKeyboardButton(text="Я подписался!", callback_data="subcheck_reactivate")],
                ])
                await bot.send_message(
                    chat_id=tg_id,
                    text=(
                        "<b>Доступ к VPN приостановлен</b>\n\n"
                        "Вы отписались от нашего канала.\n"
                        "Подпишитесь снова, чтобы восстановить бесплатный доступ."
                    ),
                    parse_mode='HTML',
                    reply_markup=notification_kb,
                )
                notified_count += 1
            except (TelegramForbiddenError, TelegramBadRequest, TelegramNotFound):
                pass
            except Exception as e:
                logger.error("Sub Clean notify error for tg_id=%s: %s", tg_id, e)

        except Exception as e:
            logger.error("Sub Clean disable error for tg_id=%s: %s", tg_id, e)
            error_count += 1

    await callback.message.edit_text(
        f"<b>Sub Clean: завершено</b>\n\n"
        f"Отключено: <b>{disabled_count}</b>\n"
        f"Уведомлено: <b>{notified_count}</b>\n"
        f"Ошибок: <b>{error_count}</b>",
        parse_mode='HTML',
    )
