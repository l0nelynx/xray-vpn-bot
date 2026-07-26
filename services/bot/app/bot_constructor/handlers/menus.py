"""Dynamic menu handler — catches screen:* callbacks and renders MenuScreen from DB."""
import logging

from aiogram import F, Router
from aiogram.types import CallbackQuery

from app.locale.utils import get_user_lang
from app.bot_constructor.keyboards.dynamic import get_dynamic_keyboard
from app.keyboards.localized import get_to_main_localized
from app.database.tariff_repository import get_screen_text
import app.database.requests as rq

logger = logging.getLogger(__name__)

router = Router()

@router.callback_query(F.data.startswith("screen:"))
async def dynamic_screen_handler(callback: CallbackQuery):
    """Render any screen stored in menu_screens by its slug."""
    slug = callback.data.removeprefix("screen:")
    tg_id = callback.from_user.id

    lang_code = await rq.get_user_language(tg_id) or "ru"
    lang = await get_user_lang(tg_id)

    keyboard = await get_dynamic_keyboard(slug, lang_code)
    if not keyboard:
        logger.warning("Dynamic screen '%s' not found in DB", slug)
        await callback.answer("Screen not found", show_alert=True)
        return

    message_text = await get_screen_text(slug, lang_code) or "​"

    try:
        await callback.message.edit_text(
            text=message_text,
            parse_mode="HTML",
            reply_markup=keyboard,
            disable_web_page_preview=True,
        )
    except Exception as e:
        logger.error("Failed to render dynamic screen '%s': %s", slug, e)
        await callback.message.edit_text(
            text="Error loading screen",
            reply_markup=get_to_main_localized(lang),
        )

    await callback.answer()
