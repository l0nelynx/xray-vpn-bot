"""
Dynamic menu handler — catches callback_data prefixed with 'screen:' and renders
the corresponding MenuScreen from DB via get_dynamic_keyboard().
Sets FSM state when opening payment-related screens.
"""
import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from app.locale.utils import get_user_lang
from app.keyboards.localized import get_dynamic_keyboard, get_to_main_localized
from app.database.tariff_repository import get_screen_text
from app.handlers.payments import PaymentState
import app.database.requests as rq

logger = logging.getLogger(__name__)

router = Router()

# Screens that need FSM state to be set so payment handlers work
PAYMENT_SCREEN_SLUGS = {"pay_methods"}


@router.callback_query(F.data.startswith("screen:"))
async def dynamic_screen_handler(callback: CallbackQuery, state: FSMContext):
    """Render any screen stored in menu_screens by its slug."""
    slug = callback.data.removeprefix("screen:")
    tg_id = callback.from_user.id

    lang_code = await rq.get_user_language(tg_id) or "ru"
    lang = await get_user_lang(tg_id)

    # Build keyboard from DB
    keyboard = await get_dynamic_keyboard(slug, lang_code)
    if not keyboard:
        logger.warning("Dynamic screen '%s' not found in DB", slug)
        await callback.answer("Screen not found", show_alert=True)
        return

    # Get message text from DB, fallback to empty
    message_text = await get_screen_text(slug, lang_code) or ""
    if not message_text:
        message_text = "\u200b"  # zero-width space to avoid empty message error

    try:
        await callback.message.edit_text(
            text=message_text,
            parse_mode="HTML",
            reply_markup=keyboard,
        )
    except Exception as e:
        logger.error("Failed to render dynamic screen '%s': %s", slug, e)
        await callback.message.edit_text(
            text="Error loading screen",
            reply_markup=get_to_main_localized(lang),
        )

    # Set FSM state for payment screens so tariff plan handlers work
    if slug in PAYMENT_SCREEN_SLUGS:
        await state.set_state(PaymentState.PaymentMethod)

    await callback.answer()
