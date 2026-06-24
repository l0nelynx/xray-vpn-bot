import logging

import app.database.requests as rq
import app.keyboards as kb
import app.api.remnawave.api as rem
from app.locale.utils import get_user_lang
from app.database.models import async_main
from app.settings import bot, admin_bot, secrets
from io import BytesIO
from aiogram.types import BufferedInputFile, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo

# Set by main.py:on_startup() after reading BotFeatureFlags from DB.
# Changing the Dashboard toggle requires a bot restart to take effect.
_legacy_constructor_enabled: bool = False

logger = logging.getLogger(__name__)

_notify = admin_bot or bot


async def start_bot():
    await _notify.send_message(secrets.get('admin_id'), 'Бот запущен')
    await async_main()
    cleaned = await rq.cleanup_stale_transactions(hours=24)
    if cleaned:
        logger.info(f"Cleaned {cleaned} stale 'created' transactions")


async def userlist():
    all_users = await rq.get_users()
    i = 0
    usrids = f"| № | Tg_id "
    for User in all_users:
        usrids = f"{usrids}\n| {i} | {User.tg_id} |"
        i = i + 1
    file_bytes = usrids.encode('utf-8')
    file = BufferedInputFile(file_bytes, filename='users.txt')
    await _notify.send_document(chat_id=secrets.get('admin_id'), document=file,
                               caption='Here is your userlist')


async def stop_bot():
    await _notify.send_message(secrets.get('admin_id'), 'Бот остановлен')


async def main_menu(message_func, menu_type, user_id: int = None, days=None, data_limit=None, link=None, user_uuid: str = None):
    """
    Display main menu with localized text and keyboards.

    Args:
        message_func: The function to send/edit message (message.answer or callback.message.edit_text)
        menu_type: Type of menu (pro, free, new)
        user_id: Telegram user ID for language lookup
        days: Remaining subscription days (for pro/free)
        data_limit: Traffic limit in bytes (None or 0 = unlimited)
        link: Subscription link
        user_uuid: RemnaWave user UUID for device count lookup
    """
    # Resolve language
    lang_code = "ru"
    if user_id:
        lang_code = await rq.get_user_language(user_id) or "ru"
    from app.locale import get_lang
    lang = get_lang(lang_code)

    if not _legacy_constructor_enabled:
        # MiniApp mode: single unified welcome for all user states.
        # miniapp_url  — direct HTTPS URL for WebAppInfo (opens app inside Telegram)
        # miniapp_tg_url — t.me/Bot/appname link for the clickable text href
        miniapp_url = secrets.get('miniapp_url', '')
        miniapp_tg_url = secrets.get('miniapp_tg_url') or miniapp_url
        text = lang.miniapp_welcome.format(miniapp_tg_url=miniapp_tg_url)
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=lang.btn_open_app, web_app=WebAppInfo(url=miniapp_url))],
            [InlineKeyboardButton(text=lang.btn_settings_info, callback_data='Settings')],
        ])
        await message_func(text, reply_markup=keyboard, parse_mode="HTML", disable_web_page_preview=True)
        return

    # Legacy constructor mode: subscription-status-specific menus.
    from app.keyboards.localized import get_main_new_localized, get_main_pro_localized, get_main_free_localized
    keyboards_map = {
        "pro": get_main_pro_localized(lang),
        "free": get_main_free_localized(lang),
        "new": get_main_new_localized(lang),
    }

    # Build subscription info block for pro/free users
    sub_info_text = ""
    if menu_type in ("pro", "free") and days is not None:
        if data_limit is None or data_limit == 0:
            traffic = "∞"
        else:
            if data_limit > (1024 * 1024 * 1024):
                traffic = f"{data_limit // (1024 * 1024 * 1024)} GB"
            else:
                traffic = f"{data_limit} GB"
        plan = "PRO" if menu_type == "pro" else "FREE"

        devices_count = 0
        if user_uuid:
            try:
                hwid_response = await rem.get_user_hwid_devices(user_uuid)
                if hwid_response:
                    devices_count = hwid_response.total
            except Exception as e:
                logger.warning("Failed to get device count for uuid %s: %s", user_uuid, e)

        sub_info_text = lang.sub_info_block.format(
            days=days, traffic=traffic, plan=plan, link=link, devices=devices_count
        ) + "\n"

    texts_map = {
        "pro": lang.start_pro + sub_info_text + lang.start_agreement,
        "free": lang.start_free + sub_info_text + lang.start_agreement,
        "new": lang.start_base + lang.start_new + lang.start_agreement,
    }

    text = texts_map.get(menu_type, texts_map["new"])
    keyboard = keyboards_map.get(menu_type, keyboards_map["new"])

    await message_func(text, reply_markup=keyboard, parse_mode="HTML", disable_web_page_preview=True)


async def main_call(message_func, menu_type, user_id: int = None, days=None, data_limit=None):
    await main_menu(message_func, menu_type, user_id, days, data_limit)
