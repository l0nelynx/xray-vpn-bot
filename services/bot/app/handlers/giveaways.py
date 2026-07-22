"""Telegram bot handlers for giveaway participation."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

import app.database.requests as rq
from app.database.models import async_session
from app.handlers.tools import check_tg_subscription
from app.settings import bot, secrets
from common_db.repo import giveaways as giveaway_repo
from common_db.repo import promos as promo_repo

giveaway_router = Router()


def _giveaway_subcheck_keyboard(giveaway_id: int, channel_url: str | None) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if channel_url:
        rows.append([InlineKeyboardButton(text="Подписаться", url=channel_url)])
    rows.append([
        InlineKeyboardButton(
            text="Я подписался!",
            callback_data=f"gw_subcheck:{giveaway_id}",
        )
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def _join_giveaway_for_user(
    tg_id: int,
    giveaway_id: int,
    *,
    channel_sub_ok: bool = True,
) -> giveaway_repo.JoinResult:
    async with async_session() as session:
        result = await giveaway_repo.join_participant(
            session,
            giveaway_id,
            tg_id,
            channel_sub_ok=channel_sub_ok,
        )
        await session.commit()
        return result


async def handle_giveaway_join(message: Message, giveaway_id: int) -> None:
    tg_id = message.from_user.id
    await rq.set_user(tg_id, message.from_user.username)

    async with async_session() as session:
        giveaway = await giveaway_repo.get_giveaway(session, giveaway_id)
        if giveaway is None:
            await message.answer("Розыгрыш не найден.", disable_web_page_preview=True)
            return
        config = giveaway_repo.normalize_config(
            giveaway_repo.parse_config(giveaway.config_json)
        )

    channel_sub_ok = True
    if config["entry_condition"] == "channel_sub":
        news_id = secrets.get("news_id")
        channel_sub_ok = await check_tg_subscription(
            bot=bot, chat_id=news_id, user_id=tg_id
        )
        if not channel_sub_ok:
            news_url = secrets.get("news_url")
            await message.answer(
                "Для участия подпишитесь на канал и нажмите «Я подписался!».",
                disable_web_page_preview=True,
                reply_markup=_giveaway_subcheck_keyboard(giveaway_id, news_url),
            )
            return

    result = await _join_giveaway_for_user(tg_id, giveaway_id, channel_sub_ok=True)
    if not result.ok:
        reasons = {
            "not_found": "Розыгрыш не найден.",
            "not_active": "Розыгрыш сейчас не активен.",
            "outside_window": "Розыгрыш ещё не начался или уже завершён.",
        }
        await message.answer(
            reasons.get(result.reason, "Не удалось принять участие."),
            disable_web_page_preview=True,
        )
        return

    if result.already_joined:
        text = f"Вы уже участвуете в розыгрыше. Билетов: {result.tickets}."
    else:
        text = f"Вы участвуете в розыгрыше! Билетов: {result.tickets}."

    if config["chance_mode"] == "dynamic" and config["ticket_sources"]:
        async with async_session() as session:
            code = await promo_repo.get_or_create_referral_code(session, tg_id)
            await session.commit()
        bot_url = secrets.get("bot_url") or ""
        ref_link = f"{bot_url}?start={code}" if bot_url else code
        text += (
            "\n\nПриглашайте друзей по вашей реф-ссылке — за выполнение условий "
            f"вы получите дополнительные билеты:\n<code>{ref_link}</code>"
        )

    await message.answer(text, parse_mode="HTML", disable_web_page_preview=True)


@giveaway_router.callback_query(F.data.startswith("gw_join:"))
async def giveaway_join_callback(callback: CallbackQuery):
    giveaway_id = int(callback.data.split(":", 1)[1])
    await handle_giveaway_join(callback.message, giveaway_id)
    await callback.answer()


@giveaway_router.callback_query(F.data.startswith("gw_subcheck:"))
async def giveaway_subcheck_callback(callback: CallbackQuery):
    giveaway_id = int(callback.data.split(":", 1)[1])
    tg_id = callback.from_user.id
    news_id = secrets.get("news_id")
    sub_ok = await check_tg_subscription(bot=bot, chat_id=news_id, user_id=tg_id)
    if not sub_ok:
        await callback.answer("Подписка не найдена. Подпишитесь и попробуйте снова.", show_alert=True)
        return
    result = await _join_giveaway_for_user(tg_id, giveaway_id, channel_sub_ok=True)
    if not result.ok:
        await callback.answer("Не удалось принять участие.", show_alert=True)
        return
    await callback.message.edit_text(
        f"Вы участвуете в розыгрыше! Билетов: {result.tickets}.",
        disable_web_page_preview=True,
    )
    await callback.answer()
