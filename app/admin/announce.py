import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
)

import app.database.requests as rq
from app.settings import secrets, bot
from .router import AdminState, is_admin, BTN_ANNOUNCE

announce_router = Router()


# ==================== Объявления (reply-кнопка) ====================

@announce_router.message(F.text == BTN_ANNOUNCE, F.from_user.id == secrets.get('admin_id'))
async def admin_announce_menu(message: Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Рассылка всем пользователям", callback_data="announce_broadcast")],
        [InlineKeyboardButton(text="Пост в канал", callback_data="announce_channel")],
    ])
    await message.answer("Выберите тип объявления:", reply_markup=kb)


# --- Рассылка всем пользователям ---

@announce_router.callback_query(F.data == "announce_broadcast")
async def announce_broadcast_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await state.set_state(AdminState.broadcast_text)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Отмена", callback_data="announce_cancel")]
    ])
    await callback.message.edit_text(
        "Введите текст рассылки (HTML-разметка поддерживается):",
        parse_mode='HTML',
        reply_markup=kb,
    )


@announce_router.message(AdminState.broadcast_text, F.from_user.id == secrets.get('admin_id'))
async def announce_broadcast_send(message: Message, state: FSMContext):
    await state.set_state(AdminState.in_admin)
    text = message.html_text

    tg_ids = await rq.get_all_user_tg_ids()
    sent = 0
    failed = 0

    status_msg = await message.answer(f"Рассылка... 0/{len(tg_ids)}")

    for i, tg_id in enumerate(tg_ids):
        try:
            # Рассылка через main bot (юзеры взаимодействуют с основным ботом)
            await bot.send_message(chat_id=tg_id, text=text, parse_mode='HTML')
            sent += 1
        except Exception:
            failed += 1
        # Обновляем статус каждые 25 сообщений
        if (i + 1) % 25 == 0:
            try:
                await status_msg.edit_text(f"Рассылка... {i + 1}/{len(tg_ids)}")
            except Exception:
                pass

    await status_msg.edit_text(
        f"<b>Рассылка завершена</b>\n\n"
        f"Всего: <b>{len(tg_ids)}</b>\n"
        f"Доставлено: <b>{sent}</b>\n"
        f"Не доставлено: <b>{failed}</b>",
        parse_mode='HTML',
    )


# --- Пост в канал ---

@announce_router.callback_query(F.data == "announce_channel")
async def announce_channel_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await state.set_state(AdminState.channel_text)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Отмена", callback_data="announce_cancel")]
    ])
    await callback.message.edit_text(
        "Введите текст поста для канала (HTML-разметка поддерживается):",
        parse_mode='HTML',
        reply_markup=kb,
    )


@announce_router.message(AdminState.channel_text, F.from_user.id == secrets.get('admin_id'))
async def announce_channel_ask_button(message: Message, state: FSMContext):
    await state.set_state(AdminState.channel_attach_btn)
    await state.update_data(channel_post_text=message.html_text)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Да, прикрепить", callback_data="announce_ch_btn:yes"),
            InlineKeyboardButton(text="Нет", callback_data="announce_ch_btn:no"),
        ],
        [InlineKeyboardButton(text="Отмена", callback_data="announce_cancel")],
    ])
    await message.answer(
        "Прикрепить кнопку со ссылкой на бота к посту?",
        reply_markup=kb,
    )


@announce_router.callback_query(F.data.startswith("announce_ch_btn:"), AdminState.channel_attach_btn)
async def announce_channel_send(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return

    attach = callback.data.split(":")[1] == "yes"
    data = await state.get_data()
    post_text = data.get("channel_post_text", "")
    await state.set_state(AdminState.in_admin)

    news_id = secrets.get("news_id")
    if not news_id:
        await callback.message.edit_text("news_id не задан в конфигурации.")
        return

    reply_markup = None
    if attach:
        # Получаем info основного бота (юзеры знают основного бота)
        bot_info = await bot.get_me()
        reply_markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Открыть бота", url=f"https://t.me/{bot_info.username}")]
        ])

    try:
        # Постим в канал через main bot (бот добавлен в канал)
        await bot.send_message(
            chat_id=news_id,
            text=post_text,
            parse_mode='HTML',
            reply_markup=reply_markup,
        )
        await callback.message.edit_text("Пост отправлен в канал.")
    except Exception as e:
        logging.error(f"Channel post error: {e}")
        await callback.message.edit_text(f"Ошибка отправки в канал: {e}")


# --- Отмена объявления ---

@announce_router.callback_query(F.data == "announce_cancel")
async def announce_cancel(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await state.set_state(AdminState.in_admin)
    await callback.message.edit_text("Отменено.")
