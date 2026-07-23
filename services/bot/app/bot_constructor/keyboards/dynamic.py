"""Dynamic keyboard builder — constructs InlineKeyboardMarkup from menu_screens DB rows."""
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo

from app.settings import secrets


async def get_dynamic_keyboard(
    screen_slug: str,
    lang_code: str = "ru",
) -> InlineKeyboardMarkup | None:
    """Build a keyboard from DB data for any screen. Returns None if screen not in DB."""
    from app.database.tariff_repository import get_screen_buttons

    buttons_data = await get_screen_buttons(screen_slug, lang_code)
    if not buttons_data:
        return None

    rows: dict[int, list] = {}
    for btn in buttons_data:
        row_idx = btn["row"]
        if row_idx not in rows:
            rows[row_idx] = []

        if btn["button_type"] == "tariff":
            rows[row_idx].append(
                InlineKeyboardButton(text=btn["text"], callback_data="tariff:root")
            )
        elif btn["button_type"] == "url" and btn.get("url"):
            rows[row_idx].append(InlineKeyboardButton(text=btn["text"], url=btn["url"]))
        elif btn["button_type"] == "webapp" and btn.get("url"):
            rows[row_idx].append(
                InlineKeyboardButton(text=btn["text"], web_app=WebAppInfo(url=btn["url"]))
            )
        else:
            rows[row_idx].append(
                InlineKeyboardButton(
                    text=btn["text"], callback_data=btn.get("callback_data", "noop")
                )
            )

    keyboard = [rows[r] for r in sorted(rows.keys())]

    miniapp_url = secrets.get("miniapp_url")
    if miniapp_url and screen_slug in ("main_new", "main_pro", "main_free"):
        label = "🚀 Открыть приложение" if lang_code == "ru" else "🚀 Open app"
        keyboard.insert(0, [InlineKeyboardButton(text=label, web_app=WebAppInfo(url=miniapp_url))])

    return InlineKeyboardMarkup(inline_keyboard=keyboard)
