import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
)

from app.settings import secrets, bot
from .router import AdminState, is_admin

messaging_router = Router()


# ==================== Отправка сообщения пользователю ====================

@messaging_router.callback_query(F.data.startswith("admin_msg:"))
async def admin_msg_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return

    tg_id = int(callback.data.split(":")[1])
    await state.set_state(AdminState.waiting_message)
    await state.update_data(target_tg_id=tg_id)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Отмена", callback_data=f"admin_user:{tg_id}")]
    ])

    await callback.message.edit_text(
        f"Введите текст сообщения для пользователя <code>{tg_id}</code>:",
        parse_mode='HTML',
        reply_markup=kb
    )


@messaging_router.message(AdminState.waiting_message, F.from_user.id == secrets.get('admin_id'))
async def admin_msg_send(message: Message, state: FSMContext):
    data = await state.get_data()
    target_tg_id = data.get("target_tg_id")
    await state.set_state(AdminState.in_admin)

    try:
        # Отправляем через main bot (юзеры взаимодействуют с основным ботом)
        await bot.send_message(
            chat_id=target_tg_id,
            text=f"Сообщение от администратора:\n\n{message.html_text}",
            parse_mode='HTML'
        )
        await message.answer(
            f"Сообщение отправлено пользователю <code>{target_tg_id}</code>",
            parse_mode='HTML',
        )
    except Exception as e:
        logging.error(f"Error sending message to {target_tg_id}: {e}")
        await message.answer(f"Ошибка отправки: {e}")
