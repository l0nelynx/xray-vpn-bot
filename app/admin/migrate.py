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


# ==================== Миграция пользователя в RemnaWave ====================

@migrate_router.callback_query(F.data.startswith("admin_migrate:"))
async def admin_migrate_user(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return

    tg_id = int(callback.data.split(":")[1])
    info = await rq.get_user_full_info_by_tg_id(tg_id)

    if not info:
        await callback.answer("Пользователь не найден", show_alert=True)
        return

    if info["api_provider"] == "remnawave":
        await callback.answer("Пользователь уже на RemnaWave", show_alert=True)
        return

    username = info["username"]
    if not username:
        await callback.answer("У пользователя нет username, миграция невозможна", show_alert=True)
        return

    await callback.message.edit_text(
        f"Миграция @{username} в RemnaWave...",
        parse_mode='HTML',
    )

    from app.handlers.tools import detect_user_api_provider, get_user_info, add_new_user_info, get_user_days

    try:
        user_info = await get_user_info(username, api="marzban")

        if user_info == 404:
            await callback.message.edit_text(
                f"Пользователь @{username} не найден в Marzban.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="Назад к карточке", callback_data=f"admin_user:{tg_id}")]
                ])
            )
            return

        expire_days = await get_user_days(user_info)
        data_limit = user_info.get("data_limit", 0)
        is_pro = user_info.get("status") == "active" and data_limit is None

        if is_pro:
            squad_id = secrets.get("rw_pro_id")
            external_squad_id = secrets.get("rw_ext_pro_id")
            description = "Migrated from Marzban (Pro) by admin"
        else:
            squad_id = secrets.get("rw_free_id")
            external_squad_id = secrets.get("rw_ext_free_id")
            description = "Migrated from Marzban (Free) by admin"

        if data_limit == 0 or data_limit is None:
            data_limit = 0
        else:
            data_limit = data_limit // (1024 * 1024 * 1024)

        new_user_info = await add_new_user_info(
            name=username,
            userid=tg_id,
            limit=data_limit,
            res_strat="month",
            expire_days=expire_days,
            api="remnawave",
            email=f"{username}@marzban.ru",
            description=description,
            squad_id=squad_id,
            external_squad_id=external_squad_id
        )

        if not new_user_info:
            await callback.message.edit_text(
                f"Ошибка создания пользователя в Beta.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="Назад к карточке", callback_data=f"admin_user:{tg_id}")]
                ])
            )
            return

        # Обновляем БД
        await rq.update_user_api_info(
            tg_id=tg_id,
            username=username,
            vless_uuid=new_user_info.get("uuid"),
            api_provider="remnawave",
        )

        subscription_url = new_user_info.get("subscription_url")

        # Отправляем пользователю сообщение об обновлении подписки (через main bot)
        try:
            import app.keyboards as kb_module
            await bot.send_message(
                chat_id=tg_id,
                text=(
                    f"Ваша подписка была обновлена!\n\n"
                    f"Больше стабильности, больше скорости, больше фичей 🚀\n\n"
                    f"Ссылка для подключения: {subscription_url}"
                ),
                parse_mode='HTML',
                reply_markup=kb_module.connect(subscription_url),
            )
        except Exception as e:
            logging.error(f"Failed to notify user {tg_id} about migration: {e}")

        # Уведомляем админа об успехе
        from app.locale.lang_ru import admin_migration_message
        await callback.message.edit_text(
            admin_migration_message.format(
                username=username,
                user_id=tg_id,
                expire_days=expire_days,
                data_limit=data_limit if data_limit > 0 else 'Без лимита',
                sub_type='Pro' if is_pro else 'Free'
            ),
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Назад к карточке", callback_data=f"admin_user:{tg_id}")]
            ])
        )

    except Exception as e:
        logging.error(f"Admin migration error for {username}: {e}")
        await callback.message.edit_text(
            f"Ошибка миграции @{username}:\n<code>{e}</code>",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Назад к карточке", callback_data=f"admin_user:{tg_id}")]
            ])
        )
